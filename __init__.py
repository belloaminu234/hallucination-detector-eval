"""halluceval: a specialized evaluator that scans agent output (code,
API calls, prose) for references to API endpoints, parameters, and ID
strings, and flags any that don't exist in a supplied ground-truth API
spec -- i.e. hallucinated API surface. Standard library only."""
