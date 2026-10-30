import os, re

status_strings = set()
results = []

for root, dirs, files in os.walk(r'E:\Projects\sms360x\backend'):
    for fn in files:
        if fn.endswith('.py'):
            path = os.path.join(root, fn)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if re.search(r'status\s*[=!]', line) or re.search(r'status\s*in', line) or re.search(r'status\s*==', line):
                    results.append((path, i, line.rstrip()))
                for m in re.finditer(r'["\']([^"\']{1,40})["\']', line):
                    val = m.group(1)
                    if val.lower() in ('open','closed','completed','escalated','cancelled','canceled','rejected','accepted','eip','overdue','under review','returned','revision required','draft','pending','in progress','escalation in progress'):
                        status_strings.add(val)
                        results.append((path, i, f'STATUS_LITERAL:{val}: {line.rstrip()}'))

print('=== STATUS STRING LITERALS FOUND ===')
for s in sorted(status_strings):
    print(f'  "{s}"')
print()
print('=== ALL LINES REFERENCING status ===')
for path, i, line in results:
    rel = os.path.relpath(path, r'E:\Projects\sms360x')
    print(f'{rel}:{i}: {line}')
