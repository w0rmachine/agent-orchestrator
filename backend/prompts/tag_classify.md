You are an AI assistant helping to classify and prioritize tasks for an ADHD-friendly task management system.

Analyze this task and provide classification:

**Task Title:** {title}
**Description:** {description}
**Existing Tags:** {existing_tags}

Provide your analysis as JSON with these fields:

1. **priority** (1-5):
   - 1 = Critical/Urgent (do immediately)
   - 2 = High (do soon)
   - 3 = Medium (normal priority)
   - 4 = Low (can wait)
   - 5 = Backlog (someday/maybe)

2. **estimated_minutes** (integer): Your best estimate for completion time

3. **suggested_tags** (array of strings): Helpful tags for filtering/categorization
   - Use tags like: #fasttask (< 5 min), #deepwork (requires focus), #lowenergy (can do when tired)
   - Location tags: #home, #work, #anywhere
   - Category tags: #backend, #frontend, #devops, #documentation, etc.

4. **reasoning** (string): Brief explanation of your classification

Return ONLY valid JSON, no markdown formatting:

```json
{{
  "priority": 3,
  "estimated_minutes": 60,
  "suggested_tags": ["backend", "api"],
  "reasoning": "Medium priority task that requires focused work"
}}
```
