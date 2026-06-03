import ast
import os

def process_file(path):
    with open(path, 'r') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except:
        return False
        
    lines = content.split('\n')
    
    # We need to process from bottom up to not mess up line numbers
    try_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            is_import_try = False
            for stmt in node.body:
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    is_import_try = True
                    break
            if not is_import_try:
                continue
            
            has_import_error = False
            for handler in node.handlers:
                if isinstance(handler.type, ast.Name) and handler.type.id == 'ImportError':
                    has_import_error = True
            
            if has_import_error:
                try_nodes.append(node)
                
    # Sort by lineno descending
    try_nodes.sort(key=lambda n: n.lineno, reverse=True)
    
    changed = False
    for node in try_nodes:
        # Check if the fallback is already gone
        # or if it has a raise directly in the first level
        has_raise = False
        for handler in node.handlers:
            if isinstance(handler.type, ast.Name) and handler.type.id == 'ImportError':
                for stmt in handler.body:
                    if isinstance(stmt, ast.Raise):
                        has_raise = True
        
        # we will replace it even if it has a raise, if the user wants all fallbacks removed
        
        start_idx = node.lineno - 1
        end_idx = node.end_lineno
        
        # extract what to keep from the try body
        keep_lines = []
        for stmt in node.body:
            # We want to keep all lines of this statement
            stmt_lines = lines[stmt.lineno - 1 : stmt.end_lineno]
            # fix indentation to match the try block's indentation
            # The try block's col_offset is node.col_offset
            # The statement's col_offset is stmt.col_offset
            indent_diff = stmt.col_offset - node.col_offset
            for line in stmt_lines:
                if len(line.strip()) > 0:
                    keep_lines.append(line[indent_diff:])
                else:
                    keep_lines.append(line)
        
        replacement = [" " * node.col_offset + "# Fallback removed"] + keep_lines
        
        lines[start_idx:end_idx] = replacement
        changed = True

    if changed:
        with open(path, 'w') as f:
            f.write('\n'.join(lines))
        print(f"Updated {path}")
        return True
    return False

def main():
    for root, _, files in os.walk('.'):
        if '.venv' in root or '.git' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                process_file(path)

if __name__ == '__main__':
    main()
