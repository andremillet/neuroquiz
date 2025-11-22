import sys
import os

def linearize_file(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # pdftotext uses \f for page breaks
    pages = content.split('\f')
    
    linearized_lines = []
    
    for i, page in enumerate(pages):
        lines = page.split('\n')
        if not lines:
            continue
            
        # Determine max line length
        max_len = 0
        for line in lines:
            max_len = max(max_len, len(line))
            
        if max_len < 10:
            linearized_lines.extend(lines)
            continue
            
        # Find gutter
        # Look in the middle 20-80%
        start_search = int(max_len * 0.3)
        end_search = int(max_len * 0.7)
        
        # We look for a column index that is a space in almost all lines that are long enough
        # Actually, a better heuristic is to find a vertical strip of spaces.
        
        gutter_scores = {}
        
        for col in range(start_search, end_search):
            score = 0
            for line in lines:
                if len(line) > col:
                    if line[col] == ' ':
                        score += 1
                    else:
                        score -= 5 # Penalty for non-space
                else:
                    score += 0.5 # Short line doesn't block gutter
            gutter_scores[col] = score
            
        # Find best column
        if not gutter_scores:
             linearized_lines.extend(lines)
             continue
             
        best_col = max(gutter_scores, key=gutter_scores.get)
        
        # If the score is too low, maybe it's not 2 columns
        if gutter_scores[best_col] < len(lines) * 0.5:
            # Treat as single column
            linearized_lines.extend(lines)
            continue
            
        # Split
        left_col = []
        right_col = []
        
        for line in lines:
            # Check if this line spans across (header/footer)
            # Heuristic: if it has text in the gutter area?
            # Or just split blindly?
            # Headers often span.
            # Let's check if the gutter area is empty for this specific line.
            # If we have text AT the split point, we shouldn't split this line, or we treat it as spanning.
            
            # But we picked a split point that is mostly spaces.
            
            if len(line) > best_col:
                left = line[:best_col].rstrip()
                right = line[best_col:].strip() # strip leading spaces from right col
                
                if left: left_col.append(left)
                if right: right_col.append(right)
            else:
                if line.strip():
                    left_col.append(line.strip())
        
        linearized_lines.extend(left_col)
        linearized_lines.extend(right_col)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linearized_lines))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python linearize_text.py <input> <output>")
        sys.exit(1)
    
    linearize_file(sys.argv[1], sys.argv[2])
    print(f"Linearized {sys.argv[1]} to {sys.argv[2]}")
