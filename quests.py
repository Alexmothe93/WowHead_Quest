#!/usr/bin/env python3

#Issues to fix/improvements:
#- Implement a HTTP timeout
#- Some quests doesn't had a description, the script put next paragraphs in description field
#- Script not finished (parsing EndText and ObjectivesText1-4, comparison with BDD, creating .sql patch)
#- Use colors or advanced logging to identify errors
#- Add percentage progress
#- More checks to do

import re
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from fcache.cache import FileCache
import csv
import mysql.connector

import config

equivalences = dict()
equivalences["database"] = ["$n", "$c", "$r"]
equivalences["en"] = ["<name>", "<class>", "<race>"]
equivalences["de"] = ["<Name>", "<Klasse>", "<Volk>"]
equivalences["es"] = ["<nombre>", "<clase>", "<raza>"]
equivalences["fr"] = ["<nom>", "<classe>", "<race>"]
equivalences["it"] = ["<name>", "<class>", "<race>"]
equivalences["pt"] = ["<name>", "<class>", "<race>"]
equivalences["ru"] = ["<name>", "<класс>", "<race>"]
equivalences["ko"] = ["<name>", "<class>", "<race>"]
equivalences["cn"] = ["<name>", "<class>", "<race>"]

MySQLconnection = mysql.connector.connect(host=config.mysql_host, port=config.mysql_port, user=config.mysql_user, password=config.mysql_password, database=config.mysql_database)
cursor = MySQLconnection.cursor()

wowheadCache = FileCache('wowheadCache', flag='cs')

def getWebPage(url):
	try:
		return BeautifulSoup(wowheadCache[url], 'html.parser')
	except KeyError:
		if config.printDebug:
			print("Getting "+url+" from the web...")
		page = requests.get(url, headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
		if page.status_code == 200:
			wowheadCache[url] = page.content
			return BeautifulSoup(page.content, 'html.parser')
		else:
			print("Error when trying to access to "+url+", status code is : "+str(page.status_code))
			return None

def getSource(category, id, lang):
	if category == "quest":
		#Try Wowhead in The Burning Crusade Classic version
		if lang == "en":
			url = "https://tbc.wowhead.com/"+category+"="+id
		else:
			url = "https://"+lang+".tbc.wowhead.com/"+category+"="+id
		soup = getWebPage(url)
		if soup.find("h1", class_="heading-size-1").text != "Quests":
			#The URL is valid
			return soup
		
		#Try Wowhead in Retail version
		if lang == "en":
			url = "https://wowhead.com/"+category+"="+id
		else:
			url = "https://"+lang+".wowhead.com/"+category+"="+id
		soup = getWebPage(url)
		if soup.find("h1", class_="heading-size-1").text != "Quests":
			#The URL is valid
			return soup
	
	print("Error, no source found for "+category+" with id : "+id)

def parseText(node):
	text = ""
	
	while True:
		if config.debugParsing:
			print("Actual node is :"+str(type(node)))
		if node is None:
			#No text to parse (no progress or completion text for example)
			print("Prout.")
			break
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
	for index, item in enumerate(equivalences[lang]):
		text = text.replace(item, equivalences["database"][index])
	
	return text.strip()

for category in config.categories:
	filename = category+'.csv'
	with open(filename, mode='w', encoding='utf-8-sig') as csv_output:
		csv_writer = csv.writer(csv_output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		if category == "quest":
			csv_writer.writerow(["id", "lang", "title", "details", "objectives", "progress", "completion"])
			#Get quests to process
			cursor.execute("""SELECT ID, LogTitle, LogDescription, QuestDescription, AreaDescription, QuestCompletionLog, ObjectiveText1, ObjectiveText2, ObjectiveText3, ObjectiveText4 FROM quest_template;""")
			quests = cursor.fetchall()
			
			for quest in quests:
				id = str(quest[0])
				for lang in config.languages:
					soup = getSource(category, id, lang)

					title = soup.find("h1", {"class": "heading-size-1"}).text.strip()
					details = parseText(soup.select('h2.heading-size-3')[0].next_element.next_element)
					objectives = parseText(soup.find("div", {"class": "block-block-bg is-btf"}).next_sibling)
					try:
						progress = parseText(soup.find(id="lknlksndgg-progress").next_element)
					except:
						progress = ""
					try:
						completion = parseText(soup.find(id="lknlksndgg-completion").next_element)
					except:
						completion = ""

					if config.printTextParsed:
						print("[" + lang + "]\nTitle: "+title+"\n\nDetails:\n"+details+"\n\nObjectives:\n"+objectives+"\n\nProgress:\n"+progress+"\n\nCompletion:\n"+completion)

					#Write to csv
					csv_writer.writerow([id, lang, title, details, objectives, progress, completion])
				print("Quest "+id+" processed.")

MySQLconnection.close()

print("DONE")
