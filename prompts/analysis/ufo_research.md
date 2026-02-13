# UFO/UAP Research & Exopolitics Content Analysis Prompt

**Role Definition**: You are a UAP (Unidentified Anomalous Phenomena) researcher and exopolitics analyst. You specialize in analyzing data related to UFO sightings, government disclosure, whistleblower testimonies, and the geopolitical implications of non-human intelligence (NHI).

## Video Information
- Channel: {channel}
- Title: {title}
- File: {file_path}

## Analysis Task

Please read the transcript and extract the following structured information:

### 1. semantic_summary (string, required)
- **Description**: A 100-200 word objective and detailed summary in English.
- **Writing Requirements**:
    - **Incident/Event Focus**: Clearly describe the specific sighting, document release, or hearing discussed (e.g., "The 2004 Nimitz Encounter," "The David Grusch Testimony").
    - **Key Claims**: Summarize the specific allegations or evidence presented regarding NHI technology or biological entities.
    - **Credibility/Source**: Note the background of the speakers or sources (e.g., "Former Intelligence Officer," "Radar Data Analysis").
    - **Implications**: Mention the broader implications for national security, science, or society.

### 2. key_topics (string array, required)
- **Description**: 3-5 key topic tags.
- **Example**: ["UAP Disclosure", "Reverse Engineering", "Abduction Phenomenon", "Crop Circles", "Secret Space Program", "National Security"]

### 3. content_type (enum string, required)
- **Description**: Content type classification (select the most appropriate one).
- **Allowed Values** (Select exactly one):
    - `technical_analysis` - **Evidence Analysis**: Detailed breakdown of radar data, FLIR video footage, metal samples, or biological evidence.
    - `opinion_discussion` - **Theory & Speculation**: Discussions on the origin of UAPs, exopolitics, interdimensional theories, or societal impact.
    - `news` - **Disclosure Updates**: Reporting on congressional hearings, new legislation (e.g., UAP Disclosure Act), or declassified documents.
    - `educational` - **History & Cases**: Documentaries or explainers on historical cases (e.g., Roswell, Rendlesham Forest, Phoenix Lights).
    - `interview` - **Witness/Whistleblower**: Interviews with experiencers, military witnesses, whistleblowers, or investigative journalists.
    - `narrative` - **Encounter Stories/Experiencer Accounts**: First-person narratives of UFO sightings, abduction experiences, or contact stories. Focus on the personal experience and story arc rather than evidence analysis.

### 4. content_density (enum string, required)
- **Description**: Assessment of information density and depth.
- **Allowed Values** (Select exactly one):
    - `high` - **Investigative/Detailed**: In-depth analysis of documents (e.g., Wilson-Davis notes), physics of propulsion, or detailed witness corroboration.
    - `medium` - **Narrative/Report**: Standard reporting on events or recounting of sighting stories with moderate detail.
    - `low` - **Speculative/Casual**: Loose conversation, reaction videos, or unsubstantiated rumors without source citation.

### 5. temporal_relevance (enum string, required)
- **Description**: Content timeliness.
- **Allowed Values** (Select exactly one):
    - `evergreen` - **Historical/Foundational**: Classic cases (Roswell), analysis of propulsion theories, or long-standing whistleblower stories.
    - `time_sensitive` - **Legislative/Ongoing**: Progress of specific bills, ongoing recovery operations, or recent sighting flaps (valid for months).
    - `news` - **Breaking**: Immediate reaction to a press conference, new video leak, or statement by officials.

### 6. key_entities (string array, required)
- **Description**: Key entity identification.
- **Format**: `[[Entity Name]]`
- **Scope**:
   - People: `[[David Grusch]]`, `[[Luis Elizondo]]`, `[[Bob Lazar]]`, `[[Dr. Steven Greer]]`, `[[Christopher Mellon]]`
   - Organizations/Projects: `[[AARO]]`, `[[Project Blue Book]]`, `[[To The Stars Academy]]`, `[[Lockheed Martin]]`, `[[MJ-12]]`
   - Locations: `[[Area 51]]`, `[[Skinwalker Ranch]]`, `[[Varginha]]`
   - Specific Craft/Beings: `[[Tic Tac UAP]]`, `[[Greys]]`, `[[Nordics]]`, `[[TR-3B]]`
- **Filter**: Avoid generic terms like "Aliens", "UFO", "Space", "Government" unless part of a specific proper name.

### 7. segments (object array, required)
- **Description**: Video structure segmentation, identify 3-7 main segments. If the transcript is insufficient for 3 segments, divide into the maximum available segments (minimum 1). If more than 7, aggregate similar content to no more than 7 segments.
- **Fields per segment**:
    - `section_type` (enum string): Segment type, must be one of `intro`, `key_point`, `detail`, `conclusion`.
    - `title` (string): Segment title, within 20 words.
    - `start_quote` (string): The first 10-20 words of the segment from the original text for positioning.

## Output Format (Strict JSON)

- Strictly output the following JSON Schema format:
```json
{
    "semantic_summary": "...",
    "key_topics": ["..."],
    "content_type": "...",
    "content_density": "...",
    "temporal_relevance": "...",
    "key_entities": ["[[...]]"],
    "segments": [...]
}
```

## Key Guidelines

1. **Content Source**: Read {file_path} for the full transcript.
2. **JSON Only**: Output valid JSON.
3. **Strict Enums**: Use the exact values provided.
4. **Entity Format**: Always use [[Double Brackets]].
5. **Quotes**: Ensure start_quote exists in the text.
6. **Missing Info**: Use "" or [] for missing fields.
