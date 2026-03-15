from transformers import AutoModel, AutoTokenizer, AutoModelForCausalLM, LlamaForCausalLM, LlamaTokenizerFast
from peft import PeftModel  # 0.5.0
import torch
# seed = 42
# torch.manual_seed(seed)
# torch.cuda.manual_seed_all(seed)
# # Optional: For absolute hardware-level determinism (can slow down performance)
# torch.backends.cudnn.deterministic = True
# torch.backends.cudnn.benchmark = False


# Load Models
base_model = "meta-llama/Meta-Llama-3-8B" 
peft_model = "FinGPT/fingpt-mt_llama3-8b_lora"
tokenizer = LlamaTokenizerFast.from_pretrained(base_model, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
model = LlamaForCausalLM.from_pretrained(base_model, trust_remote_code=True, device_map = "cuda:0")
model = PeftModel.from_pretrained(model, peft_model)
model = model.eval()


news1 = "It takes more than Nvidia's chips to build the world's data centers"
news2 = """

Nvidia (NVDA) is winning the global AI explosion. The company's chips are the most wanted in the world, with hyperscalers ranging from Amazon (AMZN) and Google (GOOG, GOOGL) to Meta (META) and Microsoft (MSFT) spending billions to pack them into their data centers.

That's been a boon for Nvidia's bottom line. Its full-year revenue has jumped from $26.9 billion in 2022 to $215.9 billion in 2025 and is expected to top $358.7 billion in 2026. That has also given the company’s stock price a major boost.

But Nvidia isn't the only company driving the AI build-out. While it develops the chips that are at the center of the AI world, Nvidia doesn't actually put them into data centers. Sure, you've likely seen Nvidia's sleek black-and-gold servers at its events, but those are reference designs, not the actual servers that go into data centers.

Nvidia's partners, including the likes of Dell (DELL), Hewlett Packard Enterprise (HPE), and Foxconn, actually build the massive arrays of computers that power AI models and services.

"What over the years Nvidia has brought to the table has been the GPUs, obviously, then moving into [data processing units] and [network interface cards] ... all the drivers, [software development kits], some of the toolkit that needs to be delivered for those silicon technologies," said Chris Davidson, vice president of high-performance computing and AI customer solutions at HPE. "But really, at the end of the day, without a solution integrator to put it all together, those are just bits and bobs. Those are just the basic components."""
news3 = "Apple reduced it's work force by 10,000 people yesterday."

# Make prompts
prompt = [
    "Instruction: What is the sentiment of this news? Please choose an answer from {negative/neutral/positive}\n" + f"Input: {news1}\n" + "Answer: "]
# f'''Instruction: What is the sentiment of this news? Please choose an answer from {{negative/neutral/positive}}
# Input: {news2}
# Answer: '''
# ]

# Set device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
tokens = tokenizer(prompt, return_tensors='pt', padding=True, truncation=True, add_special_tokens=False).to(device)
print(f"Input token shape: {tokens['input_ids'].shape}")
print(f"Generating tokens...")

responses = []
for i in range(1):

    res = model.generate(
        **tokens,
        max_new_tokens=50,
        min_new_tokens = 2,
        do_sample=False,
        temperature=0.7,
        top_p=0.95,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id
    )
    responses.append(res)
    print(f"Generation: {i}")
print(f"Output token shape: {res.shape}")
print(f"New tokens generated: {res.shape[1] - tokens['input_ids'].shape[1]}")
res_sentences_multiple = []
for res in responses:
    res_sentences = [tokenizer.decode(i, skip_special_tokens=False) for i in res]
    res_sentences_multiple.append(res_sentences)
print(f"\nFull decoded outputs:")
for res_senstences in res_sentences_multiple:
    for idx, sentence in enumerate(res_sentences):
        print(f"\n--- Output {idx+1} ---")
        print(sentence)

print("\n\nExtracted sentiment for each response:")
out_text_list = []
for res_sentences in res_sentences_multiple:
    out_text = [o.split("Answer:")[1] if "Answer:" in o else o for o in res_sentences]
    out_text_list.append(out_text)
# Show results
for i, out_text in enumerate(out_text_list):
    print(f"Generation: {i}")
    for sentiment in out_text:
        print(sentiment)
