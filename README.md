melon is a custom news feed bot for slack

tracks keywords, scans news (and filters noises) and pings only when smth solid happens

### features:
#### tracking:
- keyword tracking (per user and isolated by slack id)
- gapless serial numbers
- soft deletion to stop tracking so that history stays

#### sources:
- google news RSS 
- per user custom sources, global or per tracking
- global sources apply to all trackings unless overridden

#### signal detection:
- scrape raw headlines per topic
- embed headlines, clusetr near duplicate ones via cosine similarity (idk threshold yet)
- pick cluster leader 
- sends cluster leader + last 3 stored summaries to gemini 1.5 flash 
- JSON returned by g-1.5-flash 

#### slack commands:
- /mel-help - list all commands + FAQs
- /mel-track {keyword} -  start tracking
- /mel-active - list all active trackings with serials 
- /mel-edit {serial} -  customise sources for one tracking 
- /mel-edit global - customise sources for all trackings 

### delivery:
- cron worker loop unique topics not unique users
- one gemini call per topic per cycle regardless of sub count
- fan out to all users tracking that topic 

### resilience:
- dedup enforced at DB level 
- runs as daemon loop 
- exponential backoff on gemini 429s
