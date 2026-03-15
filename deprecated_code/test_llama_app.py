import ollama
import time

# 1. Define your "Rules" (The Instructions)
instructions = """
You are a news analyst. For every headline/section provided:
1. Rate the 'Sentiment' as Positive, Neutral, or Negative.
3. Extract the main 'Company' mentioned and reply with the ticker symbol of the company. If there is no associated publicly traded company, reply with "None" for the ticker.
Response Format: [Sentiment] | [Ticker]
"""

# 2. Your "Data" (The news sections)
news_sections = [
    "NVIDIA shares soared 5% today after announcing a new Blackwell chip breakthrough.",
    "Global oil prices remained steady despite ongoing talks in the Middle East.",
    "Microsoft faces new antitrust probe from the EU regarding cloud licensing.",
    "It takes more than Nvidia's chips to build the world's data centers",
    "Apple reduced it's work force by 10,000 people yesterday.",
    """
    Nvidia (NVDA) is winning the global AI explosion. The company's chips are the most wanted in the world, with hyperscalers ranging from Amazon (AMZN) and Google (GOOG, GOOGL) to Meta (META) and Microsoft (MSFT) spending billions to pack them into their data centers.

    That's been a boon for Nvidia's bottom line. Its full-year revenue has jumped from $26.9 billion in 2022 to $215.9 billion in 2025 and is expected to top $358.7 billion in 2026. That has also given the company’s stock price a major boost.

    But Nvidia isn't the only company driving the AI build-out. While it develops the chips that are at the center of the AI world, Nvidia doesn't actually put them into data centers. Sure, you've likely seen Nvidia's sleek black-and-gold servers at its events, but those are reference designs, not the actual servers that go into data centers.

    Nvidia's partners, including the likes of Dell (DELL), Hewlett Packard Enterprise (HPE), and Foxconn, actually build the massive arrays of computers that power AI models and services.

    "What over the years Nvidia has brought to the table has been the GPUs, obviously, then moving into [data processing units] and [network interface cards] ... all the drivers, [software development kits], some of the toolkit that needs to be delivered for those silicon technologies," said Chris Davidson, vice president of high-performance computing and AI customer solutions at HPE. "But really, at the end of the day, without a solution integrator to put it all together, those are just bits and bobs. Those are just the basic components.
    """
]

# 3. The Loop (Processing each section)
for i in range(100):
    for section in news_sections:
        start = time.time()
        response = ollama.chat(
            model='llama3.1',
            messages=[
                {'role': 'system', 'content': instructions}, # The Rules
                {'role': 'user', 'content': section},        # The Data
            ]
        )
        end = time.time()
        print(f"Generation time: {end - start:.4f} seconds")
        print(f"Result: {response['message']['content']}\n")