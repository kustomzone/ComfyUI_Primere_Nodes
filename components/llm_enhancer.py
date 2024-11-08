from pathlib import Path
import torch
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer, AutoModelForSeq2SeqLM, set_seed, GPT2Tokenizer, GPT2LMHeadModel, T5Tokenizer, T5ForConditionalGeneration, BloomTokenizerFast, BloomForCausalLM, BertTokenizer, BertForMaskedLM, DebertaV2Model, DebertaV2Config, DebertaV2Tokenizer, DebertaV2ForSequenceClassification, AlbertTokenizer, AlbertModel
from transformers.models.deberta.modeling_deberta import ContextPooler
from ..components.tree import PRIMERE_ROOT
import os
import json
import random

class PromptEnhancerLLM:
    def __init__(self, model_path: str = "flan-t5-small"):
        model_access = os.path.join(PRIMERE_ROOT, 'Nodes', 'Downloads', 'LLM', model_path)
        self.model_path = model_path

        if "t5" in model_path.lower():
            self.tokenizer = T5Tokenizer.from_pretrained(model_access, clean_up_tokenization_spaces=False, ignore_mismatched_sizes=True)
            try:
                self.model = T5ForConditionalGeneration.from_pretrained(model_access, ignore_mismatched_sizes=True, device_map="auto")
            except Exception:
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_access, ignore_mismatched_sizes=True)
        elif "bloom-" in model_path.lower():
            self.tokenizer = BloomTokenizerFast.from_pretrained(model_access, clean_up_tokenization_spaces=False, ignore_mismatched_sizes=True)
            self.model = BloomForCausalLM.from_pretrained(model_access, ignore_mismatched_sizes=True, device_map="auto")
        elif "bert" in model_path.lower() and "deberta" not in model_path.lower() and "albert" not in model_path.lower():
            self.tokenizer = BertTokenizer.from_pretrained(model_access, clean_up_tokenization_spaces=False, ignore_mismatched_sizes=True)
            self.model = BertForMaskedLM.from_pretrained(model_access, ignore_mismatched_sizes=True, return_dict=True, is_decoder=False)
        elif "deberta-" in model_path.lower():
            self.tokenizer = DebertaV2Tokenizer.from_pretrained(model_access, clean_up_tokenization_spaces=False)
            self.config = DebertaV2Config.from_pretrained(model_access)
            self.model = AutoModel.from_pretrained(model_access, ignore_mismatched_sizes=True)
            # self.config = self.model.config
        elif "albert-" in model_path.lower():
            self.tokenizer = AlbertTokenizer.from_pretrained(model_access, clean_up_tokenization_spaces=False)
            self.model = AlbertModel.from_pretrained(model_access, ignore_mismatched_sizes=True)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(model_access, clean_up_tokenization_spaces=False)
            try:
                self.model = AutoModelForCausalLM.from_pretrained(model_access, ignore_mismatched_sizes=True)
            except Exception:
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_access, ignore_mismatched_sizes=True)

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.add_special_tokens({'pad_token': '[PAD]'})
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def enhance_prompt(self, input_text: str, seed: int = 1, precision: bool = True, configurator: str = "default_settings") -> str:
        default_settings = {
            "do_sample": True,
            "temperature": 0.5,
            "top_k": 12,
            "max_length": 100,
            "num_return_sequences": 1,
            "repetition_penalty": 1.4,
            "penalty_alpha": 0.6,
            "no_repeat_ngram_size": 1,
            "early_stopping": False,
            "top_p": 0.4,
            "num_beams": 6,
        }

        variant_params = configVariants(configurator)
        configurator_name = 'high quality'
        if 'ConfigName' in variant_params:
            configurator_name = variant_params['ConfigName']
            del variant_params['ConfigName']
        instruction = f"Convert text to {configurator_name} stable diffusion text-to-image prompt: "
        settings = {**default_settings, **variant_params}

        if seed is not None and int(seed) > 1:
            random.seed(seed)
            newseed = random.randint(1, (2**32) - 1)
            set_seed(newseed)
            torch.manual_seed(newseed)
        else:
            set_seed(1)
            torch.manual_seed(1)

        if precision == False:
            self.model.half()

        with torch.no_grad():
            if "deberta-" in self.model_path.lower():
                inputs = self.tokenizer(instruction + input_text, return_tensors="pt") # .to(self.device)
                self.config.temperature = 1.0
                self.config.top_p = 1.0
                self.config.top_k = 50
                pooler = ContextPooler(self.config)

                outputs = self.model(inputs)
                encoder_layer = outputs[0]
                pooled_output = pooler(encoder_layer)
                enhanced_text = self.tokenizer.decode(pooled_output[0], skip_special_tokens=True)
                print(enhanced_text)
                exit()
                # enhanced_text = outputs # .replace(instruction + input_text, '').strip()
            elif "albert-" in self.model_path.lower():
                inputs = self.tokenizer(instruction + input_text, return_tensors="pt")
                outputs = self.model(inputs["input_ids"])
                last_hidden_states = outputs.last_hidden_state.argmax(dim=-1)
                enhanced_text = self.tokenizer.decode(last_hidden_states[0], skip_special_tokens=True)
                print(enhanced_text)
                exit()
                # enhanced_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True).replace(instruction + input_text, '').strip()
            else:
                self.model.to(self.device)
                inputs = self.tokenizer(instruction + input_text, return_tensors="pt", max_length=512, truncation=True).to(self.device)
                attention_mask = None
                if "attention_mask" in inputs:
                    attention_mask = inputs["attention_mask"]

                outputs = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=attention_mask,
                    **settings,
                    pad_token_id=self.tokenizer.eos_token_id
                )
                enhanced_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        return enhanced_text.replace(instruction + input_text, '').replace('<pad>', '').replace('image prompt:', '').replace('prompt:', '').replace('\\', '').replace('\\\n', ' ').replace('\\n', ' ').strip('.-,: ')

def PrimereLLMEnhance(modelKey = 'flan-t5-small', promptInput = 'cute cat', seed = 1, precision = True, configurator = "default"):
    model_access = os.path.join(PRIMERE_ROOT, 'Nodes', 'Downloads', 'LLM', modelKey)
    if os.path.isdir(model_access) == True:
        enhancer = PromptEnhancerLLM(modelKey)
        enhanced = enhancer.enhance_prompt(promptInput, seed=seed, precision=precision, configurator=configurator)
        return enhanced
    else:
        return False

def getConfigKeys():
    CONFIG_FILE = os.path.join(PRIMERE_ROOT, 'json', 'llm_enhancer_config.json')
    CONFIG_FILE_EXAMPLE = os.path.join(PRIMERE_ROOT, 'json', 'llm_enhancer_config.example.json')

    if Path(CONFIG_FILE).is_file() == True:
        CONFIG_SOURCE = CONFIG_FILE
    else:
        CONFIG_SOURCE = CONFIG_FILE_EXAMPLE

    ifConfigExist = os.path.isfile(CONFIG_SOURCE)
    if ifConfigExist == True:
        with open(CONFIG_SOURCE, 'r') as openfile:
            try:
                llm_config = json.load(openfile)
                return list(llm_config.keys())
            except ValueError as e:
                return None
    else:
        return None

def configVariants(variant):
    CONFIG_FILE = os.path.join(PRIMERE_ROOT, 'json', 'llm_enhancer_config.json')
    CONFIG_FILE_EXAMPLE = os.path.join(PRIMERE_ROOT, 'json', 'llm_enhancer_config.example.json')

    if Path(CONFIG_FILE).is_file() == True:
        CONFIG_SOURCE = CONFIG_FILE
    else:
        CONFIG_SOURCE = CONFIG_FILE_EXAMPLE

    ifConfigExist = os.path.isfile(CONFIG_SOURCE)
    if ifConfigExist == True:
        with open(CONFIG_SOURCE, 'r') as openfile:
            try:
                llm_config = json.load(openfile)
                if variant in llm_config:
                    return llm_config[variant]
                else:
                    return {}
            except ValueError as e:
                return {}
    else:
        return {}