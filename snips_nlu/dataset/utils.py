
from snips_nlu.constants import (
    DATA, ENTITIES, ENTITY, INTENTS, TEXT, UTTERANCES)
from snips_nlu.entity_parser.builtin_entity_parser import is_gazetteer_entity


def extract_utterance_entities(dataset):
    entities_values = {ent_name: set() for ent_name in dataset[ENTITIES]}

    for intent in dataset[INTENTS].values():
        for utterance in intent[UTTERANCES]:
            for chunk in utterance[DATA]:
                if ENTITY in chunk:
                    entities_values[chunk[ENTITY]].add(chunk[TEXT].strip())
    return {k: list(v) for k, v in entities_values.items()}


def extract_intent_entities(dataset, entity_filter=None):
    intent_entities = {intent: set() for intent in dataset[INTENTS]}
    for intent_name, intent_data in dataset[INTENTS].items():
        for utterance in intent_data[UTTERANCES]:
            for chunk in utterance[DATA]:
                if ENTITY in chunk:
                    if entity_filter and not entity_filter(chunk[ENTITY]):
                        continue
                    intent_entities[intent_name].add(chunk[ENTITY])
    return intent_entities


def extract_entity_values(dataset, apply_normalization):
    from snips_nlu_utils import normalize

    entities_per_intent = {intent: set() for intent in dataset[INTENTS]}
    intent_entities = extract_intent_entities(dataset)
    for intent, entities in intent_entities.items():
        for entity in entities:
            entity_values = set(dataset[ENTITIES][entity][UTTERANCES])
            if apply_normalization:
                entity_values = {normalize(v) for v in entity_values}
            entities_per_intent[intent].update(entity_values)
    return entities_per_intent


def get_text_from_chunks(chunks):
    return "".join(chunk[TEXT] for chunk in chunks)


def get_dataset_gazetteer_entities(dataset, intent=None):
    if intent is not None:
        return extract_intent_entities(dataset, is_gazetteer_entity)[intent]
    return {e for e in dataset[ENTITIES] if is_gazetteer_entity(e)}


def get_stop_words_whitelist(dataset, stop_words):
    """Extracts stop words whitelists per intent consisting of entity values
    that appear in the stop_words list"""
    entity_values_per_intent = extract_entity_values(
        dataset, apply_normalization=True)
    stop_words_whitelist = dict()
    for intent, entity_values in entity_values_per_intent.items():
        whitelist = stop_words.intersection(entity_values)
        if whitelist:
            stop_words_whitelist[intent] = whitelist
    return stop_words_whitelist
