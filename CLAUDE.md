# Working rules for this project (the owner asked for these)

1. **Change only what was asked.** If the owner asks to fix one thing, fix only that thing. Do not restyle, rename, move or "improve" anything else in the same push.
2. **Never trade one fix for another break.** Before every commit run the whole test suite (`SECRET_KEY=<32+ chars> RADIO_DEMO=1 python3 -m pytest -q`). Add a test for the behaviour you fixed. For the Android app also run the screenshot check and look at it.
3. **Do not reuse a name that already exists in a file** (a new helper once silently replaced an old one and emptied every podcast list). Search the file for the name first.
4. **Never push without the owner typing "push".** Never ask for passwords or codes.
5. **Be economical**: the owner's weekly usage is limited. No big redesigns, no extra features, no repeated rescans unless asked.
6. The site stays neutral: no religion, country or faith is preferred by default; each visitor sees his own country and can choose.
