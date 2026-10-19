import re

def format_code_snippet(code: str) -> str:
    code = code.strip()
    if '\n' in code:
        lines = [l.rstrip() for l in code.split('\n')]
        return '\n'.join(lines)
    
    # If semicolons exist, split on them
    if ';' in code:
        code = re.sub(r';\s*', ';\n', code)
        return code.strip()

    # Split sequential statements glued together with spaces
    # 1. Statement keywords: print, return, def, class, if, for, while, import, from, let, const, var, etc.
    code = re.sub(r'(?<=[)\]}\'\"\w])\s+(print\(|console\.log\(|return\b|def\b|class\b|if\b|for\b|while\b|import\b|from\b|let\b|const\b|var\b)', r'\n\1', code)
    # 2. Variable assignments e.g. 'y = x' or 'x = [1, 2, 3]'
    code = re.sub(r'(?<=[)\]}\'\"\w])\s+([a-zA-Z_]\w*\s*=[^=])', r'\n\1', code)
    # 3. Method calls on identifiers e.g. 'y.append(4)'
    code = re.sub(r'(?<=[)\]}\'\"\w])\s+([a-zA-Z_]\w*\.[a-zA-Z_]\w*\()', r'\n\1', code)

    lines = [l.strip() for l in code.split('\n') if l.strip()]
    return '\n'.join(lines)

def format_question_code_blocks(text: str) -> str:
    pattern = r"```([a-zA-Z0-9_-]*)\s*([\s\S]*?)```"
    if re.search(pattern, text):
        def repl(m):
            lang = m.group(1) or ""
            snippet = m.group(2) or ""
            formatted = format_code_snippet(snippet)
            return f"\n```{lang}\n{formatted}\n```\n"
        text = re.sub(pattern, repl, text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    # If no backticks, check if there is code after 'code snippet?' or 'code:' etc.
    code_intro_pattern = r"(^(?:.*?(?:code snippet|code|snippet|following program|following script))[:?]\s*)(.+)$"
    m = re.match(code_intro_pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        prefix = m.group(1).strip()
        body = m.group(2).strip()
        if re.search(r"[=();{}]", body) and not body.endswith("?"):
            formatted_body = format_code_snippet(body)
            return f"{prefix}\n\n```\n{formatted_body}\n```"

    return text

if __name__ == "__main__":
    cases = [
        "What is the output of the following code snippet? ```python x = [1, 2, 3] y = x y.append(4) print(x) ```",
        "Predict output: ```cpp int x = 10; int y = 20; std::cout << x + y << std::endl; ```",
        "What does this return? ```javascript const arr = [1, 2]; arr.push(3); console.log(arr.length) ```",
        "What is the output of the following code: x = [1, 2, 3] y = x y.append(4) print(x)",
    ]
    for c in cases:
        print("=== INPUT ===")
        print(c)
        print("=== FORMATTED ===")
        print(format_question_code_blocks(c))
        print()
