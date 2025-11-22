import json
import os

def main():
    # Load extracted questions
    try:
        with open('extracted_questions.json', 'r', encoding='utf-8') as f:
            extracted_qs = json.load(f)
    except FileNotFoundError:
        print("Error: extracted_questions.json not found.")
        return

    # Load existing pilot bank
    try:
        with open('banco_piloto_ten_abn.json', 'r', encoding='utf-8') as f:
            pilot_bank = json.load(f)
    except FileNotFoundError:
        print("Error: banco_piloto_ten_abn.json not found.")
        return

    # Prepare new categories
    medcel_category = {
        "nome": "Questões Extraídas - Medcel (Português)",
        "peso": "N/A",
        "questoes": []
    }
    
    review_category = {
        "nome": "Questões Extraídas - Comprehensive Review (Inglês)",
        "peso": "N/A",
        "questoes": []
    }

    # Counters for IDs
    med_count = 1
    rev_count = 1

    for q in extracted_qs:
        # Transform alternatives list to dict
        # Input: [{"letra": "A", "texto": "..."}, ...]
        # Output: {"A": "...", "B": "..."}
        alternativas_dict = {}
        for alt in q.get('alternativas', []):
            alternativas_dict[alt['letra']] = alt['texto']

        # Create new question object
        new_q = {
            "enunciado": q.get('enunciado', ''),
            "alternativas": alternativas_dict,
            "gabarito": q.get('gabarito', ''),
            "comentario": q.get('comentario', ''),
            "tema": "Geral",
            "language": q.get('language', 'pt')
        }

        # Assign ID and add to appropriate category
        source = q.get('source', '')
        if source == 'Medcel':
            new_q['id'] = f"MED-{med_count:03d}"
            medcel_category['questoes'].append(new_q)
            med_count += 1
        elif source == 'Comprehensive Review':
            new_q['id'] = f"REV-{rev_count:03d}"
            review_category['questoes'].append(new_q)
            rev_count += 1
        else:
            # Fallback or other sources
            pass

    # Append new categories to the bank
    pilot_bank['categorias'].append(medcel_category)
    pilot_bank['categorias'].append(review_category)
    
    # Update metadata
    pilot_bank['metadados']['total_questoes_extraidas'] = len(extracted_qs)
    pilot_bank['metadados']['aviso'] += " Inclui questões extraídas automaticamente de PDFs."

    # Save updated bank
    with open('banco_piloto_ten_abn.json', 'w', encoding='utf-8') as f:
        json.dump(pilot_bank, f, indent=2, ensure_ascii=False)

    print(f"Successfully added {med_count - 1} Medcel questions and {rev_count - 1} Review questions.")
    print("Updated banco_piloto_ten_abn.json")

if __name__ == '__main__':
    main()
