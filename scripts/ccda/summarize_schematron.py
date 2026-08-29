import sys
import json

d = json.load(sys.stdin)

print("ERRORS:", d["errorCount"])
print("WARNINGS:", d["warningCount"])
print("IGNORED:", d["ignoredCount"])
print()

for i, e in enumerate(d["errors"], 1):
    print(f"{i}. {e.get('description')}")
    print("   Path:", e.get("path"))
    print("   Assertion:", e.get("assertionId"))
    print()
