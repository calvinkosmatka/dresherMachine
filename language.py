from __future__ import print_function
from builtins import range
from collections import Counter, defaultdict
import math
import sys
import itertools
import re
#import tables
import threading
import os
#import main_1inventoryMover as m
#import dresher_LSA as d
class Language(object):
	def __init__(self, name, freq, phones, features, coding="binary"):
		"""	
		name		= string for language name
		phones 		= dictionary consisting of symbol:co-ordered tuple of feature values
		features	= co-ordered list of feature names (down the road potentially make this optional if using Avery&Idsardi features)
		coding		= type of feature coding. down the road can add support for Avery&Idsardi or other systems
		"""
		name = name.strip(".")
		#self._table_hierarchy_dict = dict([(feature, tables.Int8Col()) for feature in features])
		#self.table_file = tables.open_file(name + ".h5", mode="w", title = "Top level h5 file for " + name)
		#self.table_hierarchies = self.table_file.create_table("/", "hierarchies", self._table_hierarchy_dict, "Stores the good hierarchies")
		#self.table_bad_hierarchies = self.table_file.create_table("/", "bad_hierarchies", self._table_hierarchy_dict, "Stores the bad hierarchies")
		#self.table_phones = self.table_file.create_table("/", "phones", "Stores the phones and their feature values")
		#self.table_group_queries = self.table_file.create_group("/", "queries", "Group to store output from queries")
		self.name = name
		self._phones = phones
		self._features = features
		self._coding = coding
		
		self.phone_feat_dict = {k : [self._features[i] for i in range(len(self._features)) if self._phones[k][i] == 1] for k in self._phones.keys()}
		# num of languages with this inventory
		self.freq = freq 
		# set of admissible hierarchies (tuples)
		# should be accessed from outside via hierarchies propery
		# since _hierarchies might be stale if feature specs are updated
		self._hierarchies = set()
		# deprecated in favor of table_hierarchies

		# list storing distribution of hierarchy lengths
		self._hierarchyLengths = []

		# store results of queries
		self.queries = defaultdict(list)

		# internal variable whose value is True if new hierarchies need to be generated
		# this is done manually because generating hierarchies is computationally costly
		self._needsUpdate = True

		# print out info or not
		self.verbose = False
		
		# reading/writing lock for hdf5 table
		# RLock because the query method is recursive
		# Once pytables has support for simultaneous multiple read, we only
		# need to lock out querying while generating hierarchies, not 
		self._file_lock = threading.RLock()
	def log(self, *string):
		if self.verbose:
			print(*string)
	# Decorators
	def _thread_safe(function):
		def make_thread_safe(self, *args, **kwargs):
			self.log(self.name + " waiting for lock")
			with self._file_lock:
				self.log(self.name + " got lock")
				result = function(self, *args, **kwargs)
				self.log(self.name + " freeing lock")
			return result
		return make_thread_safe
	def _update_if_necessary(function):
		def perform_update_if_needed(self, *args, **kwargs):
			if self._needsUpdate:
				self._generate_hierarchies()
			return function(self, *args, **kwargs)
		return perform_update_if_needed

	def write_to_file(self, filename):
		pass
	def build_array(self, features):
		"""features is a subset of self._features
		returns feature array
		replacement for a dresher_lsa function
		"""
		return [tuple([self._phones[p][self._features.index(f)] for f in features]) for p in self._phones.keys()]

	@property
	@_update_if_necessary
	def hierarchies(self):
		#return set([self.row_to_tuple(r) for r in self.table_hierarchies])
		return self._hierarchies

	@hierarchies.setter
	def hierarchies(self, val):
		pass

	@property
	@_update_if_necessary
	def hierarchyLengths(self):
		return self._hierarchyLengths

	@hierarchyLengths.setter
	def hierarchyLengths(self, val):
		pass

	@_thread_safe
	def _generate_hierarchies(self):
		"""
		'private' method to generate allowable hierarchies based on current phones and features
		verbose = True enables old style printing
		"""

		startCombLength = int(math.ceil(math.log(len(self._phones.keys()), 2)))
		#minCombs = list(itertools.combinations(self.features, startCombLength))
		#print(len(minCombs))
		
		goodCombs=set()
		goodPerms=set()
		badPerms=set()
		
		lengths = Counter()
		counterTotal=0
		for length in range(startCombLength, len(self._phones.keys())+1):
			curCombs = list(itertools.combinations(self._features, length))
			for curComb in curCombs:
				# self._phones
				# self._features
				phoneFeatArray = self.build_array(curComb)
				
				# A combination of features is permissible if it distinguishes all phonemes
				# i.e. each row of the phoneFeatArray generated by the comb. must be unique
				if len(phoneFeatArray) == len(set(phoneFeatArray)):
					#add working feature set to set of sets
					goodCombs.add(frozenset(curComb))
					curPerms = list(itertools.permutations(curComb))
					for perm in curPerms:
						# immediately check for ordered containment
						try:
							for i in range(len(perm)):
								if tuple(perm[0:i+1]) in goodPerms:
									# means that there are redundant features at the tail
									#print("caught in first pass")
									#print(str(perm) + " covered by " + str(perm[0:i+1]))
									raise ValueError("Bad")
								if tuple(perm[0:i+1]) in badPerms:
									# means that there is a redundant feature within permutation
									#print("caught in first pass")
									#print(str(perm) + " " + str(perm[i+1]) + " is redundant")
									raise ValueError("Bad")
						except ValueError:
							continue
						orderedArray = self.build_array(perm)
						#print(orderedArray)
						prevNumDistinct = 1
						try:
							for i in range(len(perm)):
								curArray = [row[0:i+1] for row in orderedArray]
								curNumDistinct = len(set(curArray))
								if curNumDistinct == prevNumDistinct:
									raise ValueError("Bad")
								prevNumDistinct = curNumDistinct
						except ValueError:
							badPerms.add(tuple(perm[0:i+1]))
							#r = self.table_bad_hierarchies.row
							#for f in self.table_bad_hierarchies.colnames:
							#	try:
							#		r[f] = perm[0:i+1].index(f)
							#	except ValueError:
							#		r[f] = -1
							#r.append()
							#self.table_bad_hierarchies.flush()
							#print("feature " + perm[i] + " doesn't add new information")
							#print(perm)
							continue
						#print(perm)
						#print("good")
						lengths[len(perm)] += 1
						goodPerms.add(tuple(perm))
						#r = self.table_hierarchies.row
						#for f in self.table_hierarchies.colnames:
						#	try:
						#		r[f] = perm[0:i+1].index(f)
						#	except ValueError:
						#		r[f] = -1
						#r.append()
						#self.table_hierarchies.flush()
						
			
				counterTotal+=1
				
				if self.verbose and counterTotal % 20 == 0: 
					# TODO fix gui updates
					gui_update = str(len(self._phones.keys()))+'-'+"\t"+self.name+'\t'+ str(len(goodPerms))+"\t"+str(counterTotal)+"\t"+str(len(curCombs))
					print(gui_update, end='\r\033[K')
		if self.verbose:
			gui_update = str(len(self._phones.keys()))+'-'+"\t"+self.name+'\t'+ str(len(goodPerms))+"\t"+str(counterTotal)+"\t"+str(len(curCombs))
			print(gui_update)
		self._hierarchies = goodPerms
		self._hierarchyLengths = lengths
		self._needsUpdate = False

	@_update_if_necessary
	def min_analysis(self):
		possibleLengths = self._hierarchyLengths.keys()
		self.log(self.name + "\t" + str(sum(self._hierarchyLengths.values())) + "\t" + str(min(possibleLengths)) + "\t" + str(max(possibleLengths)))
		self.log(*sorted(self._hierarchyLengths.keys()))
		return (min(possibleLengths), max(possibleLengths))
	@_update_if_necessary
	def efficiency_analysis(self):
		totalMarkedness = 0
		lowest = 0
		markednessDict = Counter()
		mostEfficient = set()
		for h in self.hierarchies:
			#print(h)
			spec = SDA(self._phones, self._features, h)
			#print(spec)
			markedness = sum([x for phone in spec.keys() for x in spec[phone] if x==1])
			markednessDict[markedness] += 1
			if 1.0/markedness > lowest:
				lowest = 1.0/markedness
				mostEfficient = set()
			if 1.0/markedness == lowest:
				mostEfficient.add(h)
		if self.verbose:
			for k in sorted(markednessDict.keys()):
				print(k, markednessDict[k], sep=":")
		return mostEfficient, markednessDict
	def check_hierarchy(self, perm):
		"""method to check whether a particular hierarchy is allowable"""
		if self._needsUpdate:
			orderedArray = self.build_array(perm)
			prevNumDistinct = 1
			try:
				for i in range(len(perm)):
					curArray = [row[0:i+1] for row in orderedArray]
					curNumDistinct = len(set(curArray))
					if curNumDistinct == prevNumDistinct:
						raise ValueError("Bad")
					prevNumDistinct = curNumDistinct
			except ValueError:
				return False
			return True
		return hierarchy in self.hierarchies
	@_thread_safe
	@_update_if_necessary
	def query(self, q):
		""" query is a string of the following form
		see help in interface.py for now
		
		"""
		#regex = re.compile(r"\A(?P<exp>.*?(?= where (?P<predicate>.*))|.*)")
		#match = re.match(regex, q)
		qsp = re.split(r"\s*where\s*", q, 1)
		try:
			searchset, _ = self.query(qsp[1])
		except IndexError:
			searchset = self.hierarchies
		criteria = re.split(r"\s*>\s*", qsp[0])
		crit = [[f for f in re.split(r"\s*,\s*", c.strip("[]"))] for c in criteria]
		for h in searchset:
			try:
				indices = [[h.index(f) for f in c] for c in crit] 
				for x, y in zip(indices, indices[1:]):
					if max(x) > min(y):
						raise ValueError("Bad")
			except ValueError:
				continue
			self.queries[q].append(h)
		return self.queries[q], len(searchset)
	# Utility for converting between hdf5 file rows and tuples
	def row_to_tuple(self, row):
		fs = [f for f in self._features if row[f] != -1]
		t = ["",] * len(fs)
		for f in fs:
			t[row[f]] = f
		return tuple(t)

def SDA(phonedict, features, hierarchy):
	"""recursive SDA algorithm (only works on good permutations)
	not sure how it would handle with bad hierarchies

	#TODO should be to integrate this into the initial generation/checking process
	as it could eliminate some steps 
	"""

	set1 = [x for x in phonedict.keys() if phonedict[x][features.index(hierarchy[0])]==1]
	set2 = [x for x in phonedict.keys() if phonedict[x][features.index(hierarchy[0])]==0]

	outdict = {}
	if len(set1) == 0:
		for x in set2:
			outdict[x] = ["u"] + SDA({x:phonedict[x] for x in set2}, features, hierarchy[1:])[x]
		return outdict
	if len(set2) == 0:
		for x in set1:
			outdict[x] = ["u"] + SDA({x:phonedict[x] for x in set1}, features, hierarchy[1:])[x]
		return outdict
	if len(set1) == 1:
		outdict[set1[0]] = [1] + ["u" for _ in range(len(hierarchy)-1)]
	if len(set2) == 1:
		outdict[set2[0]] = [0] + ["u" for _ in range(len(hierarchy)-1)]
	if len(set1) > 1:
		for x in set1:
			outdict[x] = [1] + SDA({x:phonedict[x] for x in set1}, features, hierarchy[1:])[x]
	if len(set2) > 1:
		for x in set2:
			outdict[x] = [0] + SDA({x:phonedict[x] for x in set2}, features, hierarchy[1:])[x]
	return outdict

if __name__ == "__main__":
	runMain = False
	testSDA = True
	if testSDA:
		phonedict = {"a": (1,1,1), "e": (1,0,0), "i": (0,0,1), "o": (0,0,0)}
		features = ["1", "2", "3"]
		h1 = ("1", "3")
		h2 = ("1", "2", "3")
		print(SDA(phonedict, features, h1))
		print(SDA(phonedict, features, h2))
