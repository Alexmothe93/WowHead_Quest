#!/usr/bin/env python3

#Issues to fix/improvements:
#- Implement a HTTP timeout
#- Script not finished (parsing EndText and ObjectivesText1-4, comparison with BDD, creating .sql patch)
#- Use colors or advanced logging to identify errors
#- More checks to do

import re
import csv
from datetime import datetime
import mysql.connector
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from deepdiff import DeepDiff

import config

startTime = datetime.now()

transformations = dict()
transformations["database"] = ["$n", "$c", "$r"]
transformations["en"] = ["<name>", "<class>", "<race>"]
transformations["de"] = ["<Name>", "<Klasse>", "<Volk>"]
transformations["es"] = ["<nombre>", "<clase>", "<raza>"]
transformations["fr"] = ["<nom>", "<classe>", "<race>"]
transformations["it"] = ["<name>", "<class>", "<race>"]
transformations["pt"] = ["<name>", "<class>", "<race>"]
transformations["ru"] = ["<name>", "<класс>", "<race>"]
transformations["ko"] = ["<name>", "<class>", "<race>"]
transformations["cn"] = ["<name>", "<class>", "<race>"]

equivalences = dict()
equivalences["en"] = ["",		"Description",	"Progress",	"Completion"]
equivalences["de"] = ["de.",	"", "", ""]
equivalences["es"] = ["es.",	"", "", ""]
equivalences["fr"] = ["fr.",	"Description",	"Progrès",	"Achèvement"]
equivalences["it"] = ["it.",	"", "", ""]
equivalences["pt"] = ["pt.",	"", "", ""]
equivalences["ru"] = ["ru.",	"", "", ""]
equivalences["ko"] = ["ko.",	"", "", ""]
equivalences["cn"] = ["cn.",	"", "", ""]

dbWorld = mysql.connector.connect(host=config.dbWorld_host, port=config.dbWorld_port, user=config.dbWorld_user, password=config.dbWorld_password, database=config.dbWorld_database)
cursorWorld = dbWorld.cursor()

dbCache = mysql.connector.connect(host=config.dbCache_host, port=config.dbCache_port, user=config.dbCache_user, password=config.dbCache_password, database=config.dbCache_database)
cursorCache = dbCache.cursor()

wowheadCache = dict()

print("Loading cache...")
cursorCache.execute("""SELECT * FROM cachelite;""")
cache = cursorCache.fetchall()
for element in cache:
	wowheadCache[element[0]] = element[1]
print("Cache loaded.")

def getSource(category, id, lang, extension):
	url = "https://"+equivalences[lang][0]+extension+"wowhead.com/"+category+"="+id
	try:
		return BeautifulSoup(wowheadCache[url], 'html.parser')
	except KeyError:
		if config.printDebug:
			print("Getting "+url+" from the web...")
		page = requests.get(url, headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
		if page.status_code == 200:
			soup = BeautifulSoup(page.content, 'html.parser')
			wowheadCache[url] = str(soup.find("div", {"class": "text"}))
			cursorCache.execute("INSERT INTO cachelite (url, content) VALUES (%s, %s)", (url, wowheadCache[url]))
			dbCache.commit()
			return soup.find("div", {"class": "text"})
		else:
			print("Error when trying to access to "+url+", status code is : "+str(page.status_code))
			return None

def parseText(node):
	text = ""
	
	while True:
		if config.debugParsing:
			print("Actual node is :"+str(type(node)))
		if isinstance(node, NavigableString):
			text += node
		if isinstance(node, Tag):
			if config.debugParsing:
				print("Tag is : "+node.name)
			if node.name == "h2" or node.name == "table" or node.name == "div":
				#End of the text
				break
			if node.name == "br":
				#Add newline tag
				text += "$b"
			if node.name == "b" or node.name == "script":
				#There is a disclaimer like: "This quest was marked obsolete by Blizzard and cannot be obtained or completed.", skip
				node = node.next_element
		node = node.next_element
	
	#Convert gender tags
	text = re.sub(r'<(.+?)/(.+?)>', r'$g\1:\2;', text)
	
	#Convert name, class and race tags
	for index, item in enumerate(transformations[lang]):
		text = text.replace(item, transformations["database"][index])
	
	return text.strip().replace(u'\xa0', u'')

def parseQuest(soup, lang):
	title = soup.find("h1", {"class": "heading-size-1"}).text.strip()
	objectives = parseText(soup.find("div", {"class": "block-block-bg is-btf"}).next_sibling)
	details = None
	progress = None
	completion = None
	if soup.select('h2.heading-size-3'):
		if soup.select('h2.heading-size-3')[0].text == equivalences[lang][1]:
			details = parseText(soup.select('h2.heading-size-3')[0].next_element.next_element)
		elif soup.select('h2.heading-size-3')[0].text == equivalences[lang][2]:
			progress = parseText(soup.select('h2.heading-size-3')[0].next_element.next_element)
		elif soup.select('h2.heading-size-3')[0].text == equivalences[lang][3]:
			completion = parseText(soup.select('h2.heading-size-3')[0].next_element.next_element)
	if soup.find(id="lknlksndgg-progress") != None:
		progress = parseText(soup.find(id="lknlksndgg-progress").next_element)
	if soup.find(id="lknlksndgg-completion") != None:
		completion = parseText(soup.find(id="lknlksndgg-completion").next_element)
	
	return (title, details, objectives, progress, completion)

for category in config.categories:
	filename = category+'.csv'
	with open(filename, mode='w', encoding='utf-8-sig') as csv_output:
		csv_writer = csv.writer(csv_output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		if category == "quest":
			csv_writer.writerow(["id", "lang", "title", "details", "objectives", "progress", "completion"])
			#Get quests to process
			cursorWorld.execute("""SELECT quest_template.ID, quest_template.LogTitle AS title, quest_template.QuestDescription AS details, quest_template.LogDescription AS objectives, quest_request_items.CompletionText AS progress, quest_offer_reward.RewardText AS completion FROM quest_template LEFT JOIN quest_request_items ON quest_template.ID = quest_request_items.ID LEFT JOIN quest_offer_reward ON quest_template.ID = quest_offer_reward.ID ORDER BY quest_template.ID;""")
			quests = cursorWorld.fetchall()
			progression = 0
			total = len(quests)
			
			for questDB in quests:
				id = str(questDB[0])
				print("Processing quest "+id+"... ("+str(round((progression/total)*100, 1))+" % completed)")
				progression += 1
				
				lang = "en"
				#Try Wowhead in The Burning Crusade Classic version
				extension = "tbc."
				soup = getSource(category, id, lang, extension)
				if soup.find("h1", class_="heading-size-1").text == "Quests":
					#Try Wowhead in Retail version
					extension = ""
					soup = getSource(category, id, lang, extension)
					if soup.find("h1", class_="heading-size-1").text == "Quests":
						print("Error, no source found for "+category+" with id : "+id)
						continue
				
				questParsed = parseQuest(soup, lang)
				
				if DeepDiff((questDB[0], *questParsed), questDB, ignore_string_case=True) != {}:
					print("Error, quest parsed isn't equal to original version of quest in database.")
					continue
				
				for lang in config.languages:
					if lang != "en":
						questParsed = parseQuest(getSource(category, id, lang, extension), lang)
					
					if config.printTextParsed:
						print("[" + lang + "]\nTitle: "+title+"\n\nDetails:\n"+details+"\n\nObjectives:\n"+objectives+"\n\nProgress:\n"+progress+"\n\nCompletion:\n"+completion)

					#Write to csv
					csv_writer.writerow([id, lang, *questParsed])

dbWorld.close()
dbCache.close()

print("Done in "+format(datetime.now() - startTime))
