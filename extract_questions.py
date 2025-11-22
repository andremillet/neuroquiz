import re
import json
import os

def parse_medcel(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into potential blocks (chapters?)
    # It's hard to split by chapter reliably without more markers.
    # But we can try to identify sequences of questions and sequences of answers.
    
    lines = content.split('\n')
    
    questions = []
    answers = []
    
    current_q = None
    current_a = None
    
    # Regex for Question start: "1. ", "2. ", etc. at start of line
    q_start_re = re.compile(r'^(\d+)\.\s+(.*)')
    # Regex for Alternative: "a) ", "b) " etc.
    alt_re = re.compile(r'^([a-e])\)\s+(.*)', re.IGNORECASE)
    
    # Regex for Answer block start: "Questão 1.", "Questão 2."
    a_start_re = re.compile(r'^Questão\s+(\d+)\.\s+(.*)')
    # Regex for Gabarito: "Gabarito = X"
    gab_re = re.compile(r'Gabarito\s*=\s*([A-E])', re.IGNORECASE)
    
    # We will collect all "Question" objects and "Answer" objects found in the file.
    # Since numbering resets, we need to group them.
    # Heuristic: A sequence of Questions 1..N followed by Answers 1..N
    
    blocks = []
    current_block = {'questions': [], 'answers': []}
    
    mode = 'unknown' # 'collecting_questions', 'collecting_answers'
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for Answer start first (Questão X.)
        a_match = a_start_re.match(line)
        if a_match:
            # If we were collecting questions, switch to answers
            if mode == 'collecting_questions':
                mode = 'collecting_answers'
            
            # If we see "Questão 1." and we were already collecting answers, 
            # it might be a continuation or a new block? 
            # Usually 1..N. If we see 1 again, it's a new block.
            q_num = int(a_match.group(1))
            if q_num == 1 and len(current_block['answers']) > 0:
                 # New block starts
                 blocks.append(current_block)
                 current_block = {'questions': [], 'answers': []}
                 mode = 'collecting_answers'
            
            if current_a:
                current_block['answers'].append(current_a)
            
            current_a = {
                'id': q_num,
                'text': a_match.group(2),
                'gabarito': None
            }
            continue
            
        # Check for Gabarito
        if current_a:
            gab_match = gab_re.search(line)
            if gab_match:
                current_a['gabarito'] = gab_match.group(1)
                # Append text before gabarito if any?
                # usually gabarito is on its own line or at end.
                # The regex search finds it anywhere.
                continue
            
            # Append text to current answer explanation
            # But check if it looks like a new question or something else
            if not a_start_re.match(line) and not q_start_re.match(line):
                 current_a['text'] += " " + line

        # Check for Question start (1. )
        # Only if we are NOT in the middle of an answer block?
        # Or if we are, it switches mode back to questions?
        q_match = q_start_re.match(line)
        if q_match:
            q_text = q_match.group(2)
            
            # Filter out TOC entries:
            # 1. Ends with dots and number: "..... 90"
            # 2. Very short and looks like a title (heuristic)
            if re.search(r'\.{3,}\s*\d+$', line):
                continue
            if re.search(r'\.\.\.\.\.', line):
                continue
                
            q_num = int(q_match.group(1))
            
            # If we are in answer mode
            if mode == 'collecting_answers':
                 # Only switch to questions if we see a reset (1.)
                 # Any other number (2, 3, ...) inside an answer block is likely a list item in the explanation.
                 if q_num == 1:
                     if current_a:
                         current_block['answers'].append(current_a)
                         current_a = None
                     blocks.append(current_block)
                     current_block = {'questions': [], 'answers': []}
                     mode = 'collecting_questions'
                 else:
                     # Treat as text
                     if current_a:
                         current_a['text'] += " " + line
                     continue
            
            # If we see "1." and we are already in questions, check if it's a reset
            if q_num == 1 and len(current_block['questions']) > 0:
                 # Could be a reset, or just 1, 2, 3...
                 pass
                 
            if q_num == 1 and len(current_block['questions']) > 5: # Heuristic: if we have a bunch of questions and see 1 again
                 blocks.append(current_block)
                 current_block = {'questions': [], 'answers': []}
                 mode = 'collecting_questions'
            
            if mode == 'unknown':
                mode = 'collecting_questions'

            if current_q:
                # Validate previous question before appending
                # If it has no alternatives and is very short, it might be a false positive (like a section header)
                if not current_q['alternativas'] and len(current_q['enunciado']) < 50:
                     # Likely garbage
                     current_q = None
                else:
                     current_block['questions'].append(current_q)
            
            current_q = {
                'id': q_num,
                'enunciado': q_text,
                'alternativas': [],
                'gabarito': None, # Will be filled later
                'comentario': None # Will be filled later
            }
            continue
            
        # Check for Alternatives
        if current_q and mode == 'collecting_questions':
            alt_match = alt_re.match(line)
            if alt_match:
                current_q['alternativas'].append({
                    'letra': alt_match.group(1).upper(),
                    'texto': alt_match.group(2)
                })
                continue
            
            # Append text to question
            # Ignore "Tenho domínio", "Reler", etc.
            if "Tenho domínio" in line or "Reler o comentário" in line:
                continue
            
            # Ignore page numbers or headers if they sneak in
            if re.match(r'^\d+$', line):
                continue
                
            current_q['enunciado'] += " " + line

    # Flush last items
    if current_q:
         if not current_q['alternativas'] and len(current_q['enunciado']) < 50:
             pass
         else:
             current_block['questions'].append(current_q)
    if current_a:
        current_block['answers'].append(current_a)
    blocks.append(current_block)
    
    # Now merge questions and answers in each block
    final_questions = []
    
    for block in blocks:
        qs = {q['id']: q for q in block['questions']}
        as_ = {a['id']: a for a in block['answers']}
        
        for q_id, q in qs.items():
            combined = q.copy()
            if q_id in as_:
                ans = as_[q_id]
                combined['gabarito'] = ans['gabarito']
                combined['comentario'] = ans['text']
            else:
                combined['gabarito'] = None
                combined['comentario'] = None
            
            final_questions.append(combined)
            
    return final_questions

def parse_concurso(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    questions = []
    current_q = None
    
    q_start_re = re.compile(r'^(\d+)\.\s+(.*)')
    alt_re = re.compile(r'^\(([A-E])\)\s+(.*)', re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        q_match = q_start_re.match(line)
        if q_match:
            if current_q:
                questions.append(current_q)
            current_q = {
                'id': int(q_match.group(1)),
                'enunciado': q_match.group(2),
                'alternativas': [],
                'source': 'Concurso'
            }
            continue
            
        if current_q:
            alt_match = alt_re.match(line)
            if alt_match:
                current_q['alternativas'].append({
                    'letra': alt_match.group(1).upper(),
                    'texto': alt_match.group(2)
                })
            else:
                # Append to enunciado or previous alternative?
                # Usually Concurso formatting is tight.
                # If we have alternatives, append to last alternative
                if current_q['alternativas']:
                    current_q['alternativas'][-1]['texto'] += " " + line
                else:
                    current_q['enunciado'] += " " + line
                    
    if current_q:
        questions.append(current_q)
        
    return questions

def parse_comprehensive(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    all_extracted = []
    
    current_chapter_questions = []
    current_chapter_answers = {} # Map id -> {gabarito, comentario}
    
    current_q = None
    current_a_ids = [] 
    current_comment = []
    
    mode = 'unknown' # 'questions', 'answers'
    
    q_start_re = re.compile(r'^(\d+)\.\s+(.*)')
    alt_re = re.compile(r'^([a-e])\.\s+(.*)', re.IGNORECASE)
    ans_re = re.compile(r'^QUESTION\s+(\d+)\.\s+([a-e])', re.IGNORECASE)
    
    def flush_chapter():
        nonlocal current_chapter_questions, current_chapter_answers
        # Apply answers to questions
        for q in current_chapter_questions:
            if q['id'] in current_chapter_answers:
                q['gabarito'] = current_chapter_answers[q['id']]['gabarito']
                q['comentario'] = current_chapter_answers[q['id']]['comentario']
            else:
                q['gabarito'] = None
                q['comentario'] = None
            all_extracted.append(q)
        
        current_chapter_questions = []
        current_chapter_answers = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Mode switching
        # If we are in answers mode and see "Questions", it's a new chapter
        if line.lower().startswith('questions') and not q_start_re.match(line):
             if mode == 'answers':
                 # Flush previous chapter
                 if current_q:
                     current_chapter_questions.append(current_q)
                     current_q = None
                 if current_a_ids and current_comment:
                     comment_text = " ".join(current_comment)
                     for aid in current_a_ids:
                         current_chapter_answers[aid]['comentario'] = comment_text
                     current_a_ids = []
                     current_comment = []
                     
                 flush_chapter()
                 
             mode = 'questions'
             continue
             
        # Detect "Answers" or "Answer Key"
        if line.lower() == 'answers' or line.lower() == 'answer key':
             # Finish collecting questions for this chapter
             if current_q:
                 current_chapter_questions.append(current_q)
                 current_q = None
             mode = 'answers'
             continue
             
        if mode == 'questions':
            q_match = q_start_re.match(line)
            if q_match:
                if current_q:
                    current_chapter_questions.append(current_q)
                current_q = {
                    'id': int(q_match.group(1)),
                    'enunciado': q_match.group(2),
                    'alternativas': [],
                    'source': 'Comprehensive Review'
                }
                continue
            
            if current_q:
                alt_match = alt_re.match(line)
                if alt_match:
                    current_q['alternativas'].append({
                        'letra': alt_match.group(1).upper(),
                        'texto': alt_match.group(2)
                    })
                else:
                    # Append to enunciado or last alternative
                    if current_q['alternativas']:
                        current_q['alternativas'][-1]['texto'] += " " + line
                    else:
                        current_q['enunciado'] += " " + line
                        
        elif mode == 'answers':
            # Check for Answer line
            # Try both patterns
            ans_match = ans_re.match(line)
            
            # If not standard "QUESTION 1. d", try "1. d"
            if not ans_match:
                # Simple pattern: number, dot, space, single letter (a-e or A-E)
                # We must be careful not to match "1. Some text" which is a comment starting with a number?
                # But in Answer Key, it is just "1. d".
                # Let's use a strict regex for simple answer: ^(\d+)\.\s+([a-eA-E])$
                # Or maybe with some trailing space.
                simple_match = re.match(r'^(\d+)\.\s+([a-eA-E])\s*$', line)
                if simple_match:
                    ans_match = simple_match
            
            if ans_match:
                # Only flush if we have a substantial comment
                has_real_comment = False
                if current_comment:
                    comment_text = " ".join(current_comment).strip()
                    if comment_text and not re.match(r'^\d+$', comment_text):
                        has_real_comment = True
                
                if has_real_comment:
                     comment_text = " ".join(current_comment)
                     for aid in current_a_ids:
                         current_chapter_answers[aid]['comentario'] = comment_text
                     current_a_ids = []
                     current_comment = []
                else:
                    pass
                
                q_id = int(ans_match.group(1))
                gab = ans_match.group(2).upper()
                
                current_a_ids.append(q_id)
                # If it already exists (from Answer Key), update it?
                # Or if we are in Answers (detailed), we overwrite/update.
                if q_id not in current_chapter_answers:
                    current_chapter_answers[q_id] = {'gabarito': gab, 'comentario': ''}
                else:
                    # Update gabarito just in case, and keep existing comment if any?
                    # Usually Answer Key comes first, then Answers.
                    # So we update gabarito (should be same) and prepare to add comment.
                    current_chapter_answers[q_id]['gabarito'] = gab
                
                if not has_real_comment:
                    current_comment = []
                
            else:
                # Text line, likely comment
                if re.match(r'^\d+$', line):
                    continue
                    
                if current_a_ids:
                    current_comment.append(line)
                    
    # Flush last
    if current_q:
        current_chapter_questions.append(current_q)
    if current_a_ids and current_comment:
        comment_text = " ".join(current_comment)
        for aid in current_a_ids:
            current_chapter_answers[aid]['comentario'] = comment_text
            
    flush_chapter()
            
    return all_extracted

def clean_text(text):
    if not text:
        return text
        
    # Medcel artifacts
    text = text.replace("Refazer essa questão", "")
    text = text.replace("Encontrei dificuldade para responder", "")
    text = text.replace("Tenho domínio do assunto", "")
    text = text.replace("Reler o comentário", "")
    
    # Concurso artifacts (headers/footers often merged)
    # "Concurso Público Secretaria Municipal de Saúde"
    text = re.sub(r'Concurso Público.*', '', text, flags=re.IGNORECASE)
    # "Prefeitura da Cidade do Rio de Janeiro"
    text = re.sub(r'Prefeitura da Cidade do Rio de Janeiro.*', '', text, flags=re.IGNORECASE)
    # "NEUROLOGIA" at end of line
    text = re.sub(r'NEUROLOGIA\s*$', '', text)
    # Page numbers at end " 7 "
    text = re.sub(r'\s+\d+\s*$', '', text)
    
    return text.strip()

def main():
    all_questions = []
    
    # Medcel
    if os.path.exists('/tmp/medcel_full.txt'):
        print("Parsing Medcel...")
        medcel_qs = parse_medcel('/tmp/medcel_full.txt')
        for q in medcel_qs:
            q['source'] = 'Medcel'
            q['language'] = 'pt'
            q['enunciado'] = clean_text(q['enunciado'])
            for alt in q['alternativas']:
                alt['texto'] = clean_text(alt['texto'])
        all_questions.extend(medcel_qs)
        print(f"Found {len(medcel_qs)} questions in Medcel.")
        
    # Concurso
    if os.path.exists('/tmp/concurso_linearized.txt'):
        print("Parsing Concurso...")
        concurso_qs = parse_concurso('/tmp/concurso_linearized.txt')
        for q in concurso_qs:
            q['language'] = 'pt'
            q['enunciado'] = clean_text(q['enunciado'])
            for alt in q['alternativas']:
                alt['texto'] = clean_text(alt['texto'])
            # Ensure gabarito key exists
            if 'gabarito' not in q:
                q['gabarito'] = None
        all_questions.extend(concurso_qs)
        print(f"Found {len(concurso_qs)} questions in Concurso.")

    # Comprehensive Review
    if os.path.exists('/tmp/comprehensive_full.txt'):
        print("Parsing Comprehensive Review...")
        comp_qs = parse_comprehensive('/tmp/comprehensive_full.txt')
        for q in comp_qs:
            q['language'] = 'en'
        all_questions.extend(comp_qs)
        print(f"Found {len(comp_qs)} questions in Comprehensive Review.")
        
    # Filter out questions without gabarito
    valid_questions = [q for q in all_questions if q.get('gabarito')]
    # valid_questions = all_questions
    
    print(f"Total questions found: {len(all_questions)}")
    print(f"Questions discarded (no answer): {len(all_questions) - len(valid_questions)}")
    print(f"Final valid questions: {len(valid_questions)}")

    # Save
    with open('extracted_questions.json', 'w', encoding='utf-8') as f:
        json.dump(valid_questions, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
