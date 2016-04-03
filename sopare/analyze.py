#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2015, 2016 Martin Kauss (yo@bishoph.org)

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this file except in compliance with the License. You may obtain
a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.
"""

import util
import config
import path
import imp
import os

class analyze():

    def __init__(self, debug):
        self.debug = debug
        self.util = util.util(debug, None)
        self.DICT = self.util.getDICT()
        self.plugins = [ ]
        self.dict_analysis = self.util.compile_analysis()
        self.load_plugins()
        self.first_approach = { }
        self.reset()

    def do_analysis(self, data, word_tendency, rawbuf):
        pre_results, startpos = self.pre_scan(data)
        if (self.debug):
            print ('pre_results : '+str(pre_results))
        if (pre_results == None):
            return
        first_guess = self.first_scan(pre_results, data)
        if (self.debug):
            print ('first_guess : ' + str(first_guess))
        deep_guess = self.deep_scan(first_guess, data)
        if (deep_guess != None):
            best_match = sorted(deep_guess, key=lambda x: -x[1])
            if (self.debug):
                print ('best_match : '+ str(best_match))
            readable_resaults = self.get_readable_results(best_match, pre_results, first_guess, startpos, data)
            if (len(readable_resaults) > 0):
                for p in self.plugins:
                    p.run(readable_resaults, best_match, data, rawbuf)

    def reset(self):
        self.first_approach = { }

    def load_plugins(self):
        if (self.debug):
            print ('checking for plugins...')
        pluginsfound = os.listdir(path.__plugindestination__)
        for plugin in pluginsfound:
            try:
                pluginpath = os.path.join(path.__plugindestination__, plugin)
                if (self.debug):
                    print ('loading and initialzing '+pluginpath)
                f, filename, description = imp.find_module('__init__', [pluginpath])
                self.plugins.append(imp.load_module(plugin, f, filename, description))
            except ImportError, err:
                print 'ImportError:', err

    def get_readable_results(self, best_match, pre_results, first_guess, startpos, data):
        readable_results = [ ]
        mapper = [ '' ] * len(startpos)
        for match in best_match:
            self.mapword(match, mapper, startpos)
        if (self.debug):
            print ('mapper :'+str(mapper))
        for match in mapper:
            if (self.verify_matches(first_guess, match)):
                if (match not in readable_results):
                    readable_results.append(match)
        return readable_results

    def verify_matches(self, first_guess, match):
        for guess in first_guess:
            if (guess == match):
                if ('tokencount' not in first_guess[guess]):
                    first_guess[guess]['tokencount'] = 1
                else:
                    first_guess[guess]['tokencount'] += 1
                if (first_guess[guess]['tokencount'] >= first_guess[guess]['lmin'] and first_guess[guess]['tokencount'] <= first_guess[guess]['lmax']):
                    return True
        return False

    def mapword(self, match, mapper, startpos):
        startpos = startpos.index(match[0])
        for a in range(startpos, startpos + match[5]):
            if (mapper[a] == '' and match[1] >= config.MARGINAL_VALUE):
                mapper[a] = match[2]
 
    def deep_scan(self, first_guess, data):
        deep_guess = [ ]
        for id in first_guess:
            results = first_guess[id]['results']
            lmax = first_guess[id]['lmax']
            lmin = first_guess[id]['lmin']
            for pos in results:
                if (self.debug):
                    print ('searching for ' + id + ' between ' + str(pos) + ' and ' + str(pos+lmax))
                value = self.word_compare(id, pos, lmin, lmax, data)
                if (value != None):
                    deep_guess.append(value)
                else:
                    if (self.debug):
                        print (id + ' at ' + str(pos) + ' did not pass word_compare')
        return deep_guess

    def first_scan(self, pre_results, data):
        first_guess = { }
        for a, words in enumerate(pre_results):
            for i, start in enumerate(words):
                d = data[start]
                characteristic, meta = d
                fft_max = characteristic['fft_max']
                hi, h = self.util.get_highest(fft_max)
                self.fast_compare(i, start, hi, h, first_guess)
        if not first_guess:
             if (self.debug):
                 print ('TODO: WE MAY NEED A MORE LIBERAL METHOD TO FILL first_guess ...')
        return first_guess
                
    def fast_compare(self, i, start, hi, h, first_guess):
        # we want to find potential matching words and positions 
        # based on a rough pre comparison
        for id in self.dict_analysis:
            analysis_object = self.dict_analysis[id]
            for o in analysis_object['high5']:
                dhi, dh = o
                match = self.fast_high_compare(hi, h, dhi, dh)
                if (match > 0):
                    if (id not in first_guess):
                        first_guess[id] = { 'results': [ start ], 'lmin': analysis_object['min_tokens'], 'lmax': analysis_object['max_tokens'], 'match': { start: match } }
                    else:
                        if (start in first_guess[id]['match']):
                            first_guess[id]['match'][start] += match                            
                            # Potential point to skip inner loop for faster looping
                            # but we may loose data for later stages...
                            # As we dont use the data at the moment we go for
                            # the possible performance boost.
                            break
                        else:
                            first_guess[id]['match'][start] = match
                        if (start not in first_guess[id]['results']):
                            first_guess[id]['results'].append( start )

    def fast_high_compare(self, hi, h, dhi, dh):
        match = 0
        for i, n in enumerate(hi):
            hn = h[i]
            if (len(dhi) > i):
                dn = dhi[i]
                dhn = dh[i]
                if (n == dn):
                    h_range = hn * config.INACCURACY_FAST_HIGH_COMPARE / 100 
                    if (hn - h_range <= dhn and hn + h_range >= dhn):
                        return 1
        return match

    def word_compare(self, id, start, lmin, lmax, data):
        match_array = [ ]
        pos = 0
        for a in range(start, start+lmax):
            if (a < len(data)):
                d = data[a]
                characteristic, meta = d
                if (characteristic != None):
                    tendency = characteristic['tendency']
                    fft_approach = characteristic['fft_approach']
                    fft_max = characteristic['fft_max']
                    fft_freq = characteristic['fft_freq']
                    self.token_compare(tendency, fft_approach, fft_max, fft_freq, id, pos, match_array)
                    pos += 1
        points, got_matches_for_all_tokens = self.calculate_points(id, start, match_array, lmin, lmax)
        if (points == 0):
            return None
        value = [start, points, id, lmax, match_array, got_matches_for_all_tokens]
        return value

    def calculate_points(self, id, start, match_array, lmin, lmax):
        if (self.debug):
            print ('################################################')
            print ('id = ' + str(id) + ' / ' + str(start))
            print (match_array)
        ll = len(match_array)
        match_array_counter = 0
        best_match = 0
        best_match_h = 0
        perfect_matches = 0
        perfect_match_sum = 0
        got_matches_for_all_tokens = 0
        got_matches_for_all_tokens_points = 0
        for arr in match_array:
            best_match_h = sum(arr[0])
            points = sum(arr[2])
            if (points > 0):
                got_matches_for_all_tokens_points += 1
            if (config.USE_FUZZY):
                best_match_h += sum(arr[1])
            if (best_match_h >= config.MIN_PERFECT_MATCHES_FOR_CONSIDERATION): 
                got_matches_for_all_tokens += 1
            if (best_match_h > best_match):
                check = sum(config.IMPORTANCE[0:len(arr[0])])
                best_match = best_match_h
                perfect_matches += best_match
                perfect_match_sum += check
        points = 100 * got_matches_for_all_tokens_points / ll
        if (got_matches_for_all_tokens < ll):
            if (self.debug):
                print ('dumping score because of token matches '+str(got_matches_for_all_tokens) + ' ! ' + str(ll))
            perfect_matches = perfect_matches * got_matches_for_all_tokens / ll
        if (len(match_array) < lmin or len(match_array) > lmax):
            if (self.debug):
                 print ('this seems to be a false positive as min/max token length does not match :'+str(lmin) + ' < ' + str(ll)+ ' > ' + str(lmax))
            perfect_matches = perfect_matches / 10
        if (perfect_match_sum > 0):
            perfect_matches = perfect_matches * 100 / perfect_match_sum 
            if (perfect_matches > 100):
                perfect_matches = 100
            best_match = perfect_matches * points / 100
            if (ll >= lmin and ll <= lmax):
                if (self.debug):
                    print ('-------------------------------------')
                    print ('id/start/points/perfect_matches/best_match ' + id + '/' + str(start) + '/' + str(points) + '/' + str(perfect_matches) + '/' + str(best_match))
                return best_match, got_matches_for_all_tokens
            else:
                if (self.debug):
                    print ('----------- !!! '+str(ll) +' >= '+str(lmin) + ' and ' +str(ll) + ' <= ' + str(lmax))
        else:
            if (self.debug):
    	        print ('----------- perfect_match_sum == 0')
        return 0, 0

    def pre_scan(self, data):
        posmapper = [ ]
        startpos = [ ]
        endpos = [ ]
        peaks = [ ]
        for i, d in enumerate(data):
            characteristic, meta = d
            if (characteristic != None):
                startpos.append(i)
            for m in meta:
                token = m['token']
                if (token != 'stop'):
                    if (token == 'token'):
                        posmapper.append(m['pos'])
                        endpos.append(i)
                    elif (token == 'start analysis'):
                        posmapper.append(m['pos'])
        wordpos = [ ]
        last = -1
        if (len(endpos) > 0 and len(startpos) > 0):
            for end in endpos:
                word = [ ]
                for start in startpos:
                    if (start > last):
                        word.append(start)
                if (len(word) > 0 and word not in wordpos):
                    wordpos.append(word)
                last = end
        else:
            wordpos.append(startpos)
        if (len(wordpos) == 0):
            wordpos.append(startpos)
        return wordpos, startpos

    def token_compare(self, tendency, fft_approach, fft_max, fft_freq, id, pos, match_array):
        perfect_match_array = [0] * len(config.IMPORTANCE)
        fuzzy_array = [0] * len(config.IMPORTANCE)
        tendency_array = [ ]
        counter = 0
        for dict_entries in self.DICT['dict']:
            did = dict_entries['id']
            if (id == did):
                analysis_object = self.dict_analysis[id]
                for i, characteristic in enumerate(dict_entries['characteristic']):
                    if (pos == i):
                        dict_tendency = characteristic['tendency']
                        hc = self.compare_tendency(tendency, dict_tendency, fft_freq, characteristic['fft_freq'])
                        tendency_array.append(hc)
                        dict_fft_approach = characteristic['fft_approach']
                        dict_fft_max = characteristic['fft_max']
                        perfect_match_array, fuzzy_array = self.compare_fft_token_approach(fft_approach, dict_fft_approach, fft_max, dict_fft_max, perfect_match_array, fuzzy_array)
                        counter += 1
        match_array.append([perfect_match_array, fuzzy_array, tendency_array])

    def compare_fft_token_approach(self, cfft, dfft, fft_max, dict_fft_max, perfect_match_array, fuzzy_array):
        zipped = zip(cfft, dfft, fft_max, dict_fft_max)
        cut = len(config.IMPORTANCE)
        if (len(zipped) < cut):
            cut = len(zipped)
            perfect_match_array = perfect_match_array[0:cut]
            fuzzy_array = fuzzy_array[0:cut]
        for i, z in enumerate(zipped):
            a, b, e, f = z
            if (a < cut):
                factor = 1
                e_range = e * config.INACCURACY / 100
                if (a == b and e - e_range <= f and e + e_range >= f):
                    if (a < len(config.IMPORTANCE)):
                        factor = config.IMPORTANCE[a]
                    if (a < len(perfect_match_array) and perfect_match_array[a] == 0):
                        perfect_match_array[a] = factor
                elif (b in cfft):
                    r = 0
                    g = cfft.index(b)
                    e_range = e * config.INACCURACY / 100
                    factor = 1
                    if (g < len(config.IMPORTANCE)):
                        factor = config.IMPORTANCE[g]
                    if (g < len(config.WITHIN_RANGE)):
                        r = config.WITHIN_RANGE[g]
                    if (i >= g - r and i <= g + r and e - e_range <= f and e + e_range >= f):
                        if (b < len(fuzzy_array) and fuzzy_array[b] == 0):
                            fuzzy_array[b] = factor
        return perfect_match_array, fuzzy_array

    def compare_tendency(self, c, d, cfreq, dfreq):
        convergency = 0
        if (c['len'] == d['len']):
            convergency += 40
        else:
            convergency += 2
        range = c['deg'] * config.TENDENCY_INACCURACY / 100
        if (c['deg'] - range <= d['deg'] and c['deg']+range >= d['deg']):
            convergency += 60
        else:
            convergency -= 5
        # TODO: cfreq, dfreq
        return convergency
