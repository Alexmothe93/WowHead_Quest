# [WIP] Scraper for quests from Wowhead
This script extracts the translations of the quest texts from Wowhead.
It is designed for TrinityCore with a 3.3.5a client.

# How To Use
* Python 3 is required.
```bash
git clone https://github.com/Alexmothe93/WowHead_Quest
cd ./WowHead_Quest
```
```bash
python -m pip install -r ./requirements.txt
```
```bash
cp ./config.py.dist ./config.py
```
Modify the config.py file to fit your needs.
```bash
python ./quests.py
```
The script currently generates a .csv file, but it should generate a .sql patch file when the script is finalized.
Warning - The script is not finished and produces erratic results!