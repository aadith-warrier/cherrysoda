
import argparse
import torch
 
from src.models.model_registry import get_model_wrapper
from data.loaders import load_dataset_unified
import yaml
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="configs/model/dream_7b.yaml")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--example_index", type=int, default=0)
    args = parser.parse_args()
 
    with open(args.model) as f:
        model_cfg = yaml.safe_load(f)
 
    model = get_model_wrapper(model_cfg)
    examples = load_dataset_unified(args.dataset, sample_size=args.example_index + 1)
    example = examples[args.example_index]
 
    print(f"Prompt:\n{example['prompt']}\n")
 
    messages = [{"role": "user", "content": example["prompt"]}]
    inputs = model.tokenizer.apply_chat_template(
        messages, return_tensors="pt", return_dict=True, add_generation_prompt=True
    )
    input_ids = inputs.input_ids.to(model.device)
    attention_mask = inputs.attention_mask.to(model.device)
 
    gen_cfg = model_cfg["generation"]
    with torch.no_grad():
        output = model.model.diffusion_generate(
            input_ids,
            attention_mask=attention_mask,
            max_new_tokens=gen_cfg["max_new_tokens"],
            steps=gen_cfg["num_denoising_steps"],
            output_history=False,
            return_dict_in_generate=True,
            temperature=0.0,
            top_p=None,
            alg="entropy",
            alg_temp=0.0,
        )
 
    prompt_len = input_ids.shape[1]
    generated_ids = output.sequences[0][prompt_len:]
 
    print(f"Raw generated token ids (first 40): {generated_ids[:40].tolist()}")
    print(f"eos_token_id: {model.tokenizer.eos_token_id}")
    print(f"Position of FIRST eos token (if any): "
          f"{(generated_ids == model.tokenizer.eos_token_id).nonzero()[:1].tolist()}")
 
    print("\n--- Decode WITHOUT skip_special_tokens, WITHOUT split ---")
    print(repr(model.tokenizer.decode(generated_ids.tolist())))
 
    print("\n--- Decode WITH skip_special_tokens=True ---")
    print(repr(model.tokenizer.decode(generated_ids.tolist(), skip_special_tokens=True)))
 
 
if __name__ == "__main__":
    main()
 