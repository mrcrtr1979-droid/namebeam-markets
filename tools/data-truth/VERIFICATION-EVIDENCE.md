# Per-day evidence (window = 30 characters either side of the matched text)

## Houston HVAC, OpenAI API, ONE HOUR (prompt: Who is the best HVAC company in Houston for AC repair?)
2026-09-01 | OK | not counted | literal no | extractor field no
2026-09-02 | OK | COUNTED alias='one hour' matched='One Hour' | ...ranchisor with local crews) - One Hour Heating & Air Conditioning (l... | literal yes | extractor field no
2026-09-03 | OK | COUNTED alias='one hour' matched='One Hour' | ...ntial emergency AC repairs. - One Hour Heating & Air Conditioning (l... | literal yes | extractor field no
2026-09-04 | OK | COUNTED alias='one hour' matched='One Hour' | ...lus major service franchises (One Hour, ARS/Rescue Rooter) that oper... | literal yes | extractor field no
2026-09-05 | OK | not counted | literal no | extractor field no
2026-09-06 | OK | COUNTED alias='one hour' matched='One Hour' | ...otprint and 24/7 service. - One Hour Heating & Air / Benjamin Fran... | literal yes | extractor field no
2026-09-07 | OK | not counted | literal no | extractor field no
2026-09-08 | OK | COUNTED alias='one hour' matched='One Hour' | ...ms and maintenance plans. - One Hour Heating & Air Conditioning (l... | literal yes | extractor field no
2026-09-09 | OK | COUNTED alias='one hour' matched='One Hour' | ... chains that operate locally: One Hour Heating & Air Conditioning, A... | literal yes | extractor field no
2026-09-10 | OK | COUNTED alias='one hour' matched='One Hour' | ...lity and emergency service. - One Hour Heating & Air Conditioning / ... | literal yes | extractor field no
2026-09-11 | OK | not counted | literal no | extractor field no
2026-09-12 | OK | not counted | literal no | extractor field no
2026-09-13 | OK | not counted | literal no | extractor field no
2026-09-14 | OK | COUNTED alias='one hour' matched='One Hour' | ...ties and emergency service. - One Hour Heating & Air Conditioning f... | literal yes | extractor field no
2026-09-15 | OK | COUNTED alias='one hour' matched='One Hour' | ...e Rooter (Houston branch) - One Hour Heating & Air (local franchis... | literal yes | extractor field no
2026-09-16 | OK | COUNTED alias='one hour' matched='One Hour' | ...s Plumbing, AC & Electric - One Hour / Mister Sparky franchises (l... | literal yes | extractor field no
2026-09-17 | OK | not counted | literal no | extractor field no
2026-09-18 | OK | not counted | literal no | extractor field no
2026-09-19 | OK | COUNTED alias='one hour' matched='One Hour' | ...ston locations you can check: One Hour Heating & Air Conditioning; S... | literal yes | extractor field no
2026-09-20 | OK | COUNTED alias='one hour' matched='One Hour' | ...k with local technicians. - One Hour Heating & Air Conditioning / ... | literal yes | extractor field no
2026-09-21 | OK | COUNTED alias='one hour' matched='One Hour' | ... and fast response times. - One Hour Heating & Air Conditioning / ... | literal yes | extractor field no
2026-09-22 | OK | not counted | literal no | extractor field no
2026-09-23 | OK | COUNTED alias='one hour' matched='One Hour' | ...mmended; national brands (ARS/One Hour) and reputable local shops al... | literal yes | extractor field no
2026-09-24 | OK | not counted | literal no | extractor field no
2026-09-25 | OK | COUNTED alias='one hour' matched='One Hour' | ... branches and 24/7 service. - One Hour Heating & Air Conditioning / ... | literal yes | extractor field no
2026-09-26 | OK | COUNTED alias='one hour' matched='One Hour' | ... chain that serves Houston) - One Hour Heating & Air (local franchis... | literal yes | extractor field no
2026-09-27 | OK | not counted | literal no | extractor field no
TOTAL counted 16, literal regex 'one[\\s-]*hour' on the same files 16, extractor field 0, answered days 27

## Pleasanton injury, Gemini, GJEL (prompt: I was in a car accident in Pleasanton CA. Which lawyer should I hire for my injury case?)
2026-09-01 | OK | COUNTED alias='gjel' matched='GJEL' | ... Bay Injury Specialists * **GJEL Accident Attorneys** * ... | literal yes | extractor field yes
2026-09-02 | FAILED | no answered run, failed day, not counted
2026-09-03 | FAILED | no answered run, failed day, not counted
2026-09-04 | OK | COUNTED alias='gjel' matched='GJEL' | ...rms (Covering Pleasanton) * **GJEL Accident Attorneys** (Orinda ... | literal yes | extractor field yes
2026-09-05 | FAILED | no answered run, failed day, not counted
2026-09-06 | OK | COUNTED alias='gjel' matched='GJEL' | ...ley and East Bay area: * **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-07 | OK | COUNTED alias='gjel' matched='GJEL' | ...ra Costa County courts. * **GJEL Accident Attorneys (Offices t... | literal yes | extractor field no
2026-09-08 | OK | COUNTED alias='gjel' matched='GJEL' | ... Specialty Firms:** * **GJEL Accident Attorneys** (Multipl... | literal yes | extractor field yes
2026-09-09 | FAILED | no answered run, failed day, not counted
2026-09-10 | OK | COUNTED alias='gjel' matched='GJEL' | ... in car accident cases: 1. **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-11 | OK | COUNTED alias='gjel' matched='GJEL' | ...onal Injury Specialists * **GJEL Accident Attorneys (Pleasanto... | literal yes | extractor field yes
2026-09-12 | OK | COUNTED alias='gjel' matched='GJEL' | ...or a free consultation: 1. **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-13 | OK | COUNTED alias='gjel' matched='GJEL' | ...ton and Alameda County: 1. **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-14 | OK | not counted | literal no | extractor field no
2026-09-15 | OK | COUNTED alias='gjel' matched='GJEL' | ...on and Alameda County: * **GJEL Accident Attorneys** * ... | literal yes | extractor field yes
2026-09-16 | OK | COUNTED alias='gjel' matched='GJEL' | ... Alameda County courts. * **GJEL Accident Attorneys (Bay Area ... | literal yes | extractor field no
2026-09-17 | OK | COUNTED alias='gjel' matched='GJEL' | ...nal Personal Injury Firms * **GJEL Accident Attorneys** (*Office... | literal yes | extractor field yes
2026-09-18 | FAILED | no answered run, failed day, not counted
2026-09-19 | OK | not counted | literal no | extractor field no
2026-09-20 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-21 | FAILED | no answered run, failed day, not counted
2026-09-22 | FAILED | no answered run, failed day, not counted
2026-09-23 | OK | COUNTED alias='gjel' matched='GJEL' | ...ss they win your case). 1. **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-24 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-25 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-26 | OK | COUNTED alias='gjel' matched='GJEL' | ...f them before deciding. 1. **GJEL Accident Attorneys (Pleasanto... | literal yes | extractor field yes
2026-09-27 | FAILED | no answered run, failed day, not counted
TOTAL counted 14, literal regex 'gjel' on the same files 14, extractor field 7, answered days 16

## Pleasanton injury, Gemini, GJEL (prompt: Who is the best personal injury lawyer in Pleasanton California?)
2026-09-01 | OK | COUNTED alias='gjel' matched='GJEL' | ...Serving Pleasanton #### 1. **GJEL Accident Attorneys** * **Loca... | literal yes | extractor field yes
2026-09-02 | FAILED | no answered run, failed day, not counted
2026-09-03 | FAILED | no answered run, failed day, not counted
2026-09-04 | FAILED | no answered run, failed day, not counted
2026-09-05 | FAILED | no answered run, failed day, not counted
2026-09-06 | FAILED | no answered run, failed day, not counted
2026-09-07 | OK | COUNTED alias='gjel' matched='GJEL' | ... injury representation. 2. **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-08 | FAILED | no answered run, failed day, not counted
2026-09-09 | OK | COUNTED alias='gjel' matched='GJEL' | ...yers Serving Pleasanton 1. **GJEL Accident Attorneys** * **L... | literal yes | extractor field yes
2026-09-10 | OK | COUNTED alias='gjel' matched='GJEL' | ...settlement negotiation. 3. **GJEL Accident Attorneys (East Bay ... | literal yes | extractor field no
2026-09-11 | OK | COUNTED alias='gjel' matched='GJEL' | ...easanton area: --- ### 1. **GJEL Accident Attorneys** * **Loca... | literal yes | extractor field yes
2026-09-12 | OK | COUNTED alias='gjel' matched='GJEL' | ... Alameda County courts. 2. **GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-13 | OK | COUNTED alias='gjel' matched='GJEL' | ...rs in Pleasanton** #### **1. GJEL Accident Attorneys (Pleasanto... | literal yes | extractor field no
2026-09-14 | OK | COUNTED alias='gjel' matched='GJEL' | ... "billboard" firm. #### **2. GJEL Accident Attorneys (Gillin, J... | literal yes | extractor field no
2026-09-15 | OK | not counted | literal no | extractor field no
2026-09-16 | OK | COUNTED alias='gjel' matched='GJEL' | ...s serving Pleasanton: ### 1. GJEL Accident Attorneys * **Overvi... | literal yes | extractor field no
2026-09-17 | FAILED | no answered run, failed day, not counted
2026-09-18 | OK | COUNTED alias='gjel' matched='GJEL' | ...ms in/near Pleasanton** 1. **GJEL Accident Attorneys (Pleasanto... | literal yes | extractor field yes
2026-09-19 | OK | COUNTED alias='gjel' matched='GJEL' | ...ng Pleasanton: --- ### 1. **GJEL Accident Attorneys (Pleasanto... | literal yes | extractor field yes
2026-09-20 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-21 | FAILED | no answered run, failed day, not counted
2026-09-22 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-23 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-24 | OK | COUNTED alias='gjel' matched='GJEL' | ...Law Firms in Pleasanton 1. **GJEL Accident Attorneys** * **L... | literal yes | extractor field yes
2026-09-25 | QUOTA_BLOCKED | no answered run, failed day, not counted
2026-09-26 | OK | COUNTED alias='gjel' matched='GJEL' | ...i-Valley law firm. #### 2. **GJEL Accident Attorneys (Gillick, ... | literal yes | extractor field no
2026-09-27 | FAILED | no answered run, failed day, not counted
TOTAL counted 13, literal regex 'gjel' on the same files 13, extractor field 6, answered days 14

## Pleasanton injury, Perplexity, Hosterman, both prompts pooled by day (09-01 to 09-26)
2026-09-01 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...asanton.[15] - **John Michael Hosterman** listed in Justia and FindL... | literal yes | extractor field no
2026-09-02 | FAILED | no answered run, failed day, not counted
2026-09-03 | FAILED | no answered run, failed day, not counted
2026-09-04 | FAILED | no answered run, failed day, not counted
2026-09-05 | OK | COUNTED alias='hosterman' matched='Hosterman' | ... results are: - **J. Michael Hosterman** listed in Justia and FindL... | literal yes | extractor field yes
2026-09-06 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...n M. Fuerch**, **John Michael Hosterman / The Law Offices of J. Micha... | literal yes | extractor field no
2026-09-07 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...cities.[8][19] - **J. Michael Hosterman** appears in lawyer director... | literal yes | extractor field yes
2026-09-08 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...ry firm.[20] - **John Michael Hosterman** and **Thomas Edward Sokat**... | literal yes | extractor field yes
2026-09-09 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...y cases.[14] - **John Michael Hosterman** appears in Justia's Pleasa... | literal yes | extractor field yes
2026-09-10 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman**, which is in Pleasanton and... | literal yes | extractor field yes
2026-09-11 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman** are the strongest local opt... | literal yes | extractor field yes
2026-09-12 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...le rating.[11] - **J. Michael Hosterman** listed as handling persona... | literal yes | extractor field yes
2026-09-13 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman**. GJEL has a Pleasanton offi... | literal yes | extractor field yes
2026-09-14 | OK | COUNTED alias='hosterman' matched='Hosterman' | ... results are: - **J. Michael Hosterman** listed in a firm profile f... | literal yes | extractor field yes
2026-09-15 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...bility.[6][11] - **J. Michael Hosterman** a Pleasanton-based attorne... | literal yes | extractor field yes
2026-09-16 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman** listed in Pleasanton with ... | literal yes | extractor field yes
2026-09-17 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...d clients.[15] - **J. Michael Hosterman** Pleasanton-based personal ... | literal yes | extractor field yes
2026-09-18 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman** listed in Pleasanton and n... | literal yes | extractor field yes
2026-09-19 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...tedly, including **J. Michael Hosterman**, **Thomas Edward Sokat**, *... | literal yes | extractor field yes
2026-09-20 | OK | COUNTED alias='hosterman' matched='Hosterman' | ... search results, **J. Michael Hosterman**, **Thomas Edward Sokat**, a... | literal yes | extractor field yes
2026-09-21 | OK | COUNTED alias='hosterman' matched='Hosterman' | ... the results: - **J. Michael Hosterman** listed in Pleasanton with ... | literal yes | extractor field yes
2026-09-22 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...listings are: - **J. Michael Hosterman** listed in Justia and Attor... | literal yes | extractor field yes
2026-09-23 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...rea options*: - **J. Michael Hosterman** is listed in Justia and Att... | literal yes | extractor field yes
2026-09-24 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...e **Law Offices of J. Michael Hosterman**.[1][5][12][16][17] If you ... | literal yes | extractor field yes
2026-09-25 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman**, because they appear in loc... | literal yes | extractor field yes
2026-09-26 | OK | COUNTED alias='hosterman' matched='Hosterman' | ...The Law Offices of J. Michael Hosterman**; both are listed as Pleasan... | literal yes | extractor field yes
TOTAL counted 23, literal regex 'hosterman' on the same files 23, extractor field 21, answered days 23

