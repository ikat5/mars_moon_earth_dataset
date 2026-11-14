# Demo script (~3 minutes)

Start the server a few minutes before recording, so imagery prewarming has finished (see the [runbook](../analysis/RUNBOOK.md)). Use a laptop with a real GPU, open `http://localhost:8000`, and close other tabs. Times are approximate.

| Time | Action | Say |
|---|---|---|
| 0:00 | Page open on Mars | "TerraTwin finds Earth regions whose regional terrain resembles a Moon or Mars region, and shows why." |
| 0:10 | Enter Mars 18.41, 77.69 → **Select** | "This is Jezero crater's centre. TerraTwin outlines the ~15 km regional cell containing the point and shows its measured slopes, relief and roughness. These describe the whole cell, not the click." |
| 0:30 | Keep *Historical dry/barren screening*; type a purpose ("rover navigation on gentle plains"); **Find Earth candidates** | "Both modes use the same terrain score. This one only allows Earth cells that were barren and arid in historical data." |
| 0:45 | Watch the reveal | "The search ran over the real dataset. We move to Earth, and the best match's actual footprint appears at its true location in the Gobi, with resemblance 99.7. This is a data match, not a route or a certified site." |
| 1:05 | Evidence tab: scroll the table and context | "Each measurement, its difference, tolerance and points. The largest mismatch is highlighted. Earth land cover and aridity are shown with their dates and don't affect the score." |
| 1:25 | Results → tick #1 and #2 → Compare | "The comparison shows which measurement separates two close candidates, and warns that sub-point differences aren't meaningful." |
| 1:45 | Local studies → Gobi → Show footprint | "The next step is finer evidence. At Gobi, 30 m elevation shows slope variation hidden in the regional summary." |
| 2:05 | Results → **Investigation brief** | "Everything exports: JSON, GeoJSON and a printable brief with sources, versions, limitations and proposed next measurements." |
| 2:20 | Return to target → example *Jezero centre within 500 km of Sylhet* | "Honest answers matter. No Earth region within 500 km of Sylhet passes these filters. TerraTwin says so and never relaxes the filters silently." |
| 2:40 | Example *Shackleton crater centre* | "At Shackleton, the integrated terrain data is missing, so TerraTwin reports insufficient evidence instead of inventing a match." |
| 2:55 | Close | "TerraTwin: a reasoned, inspectable shortlist of Earth analogs for a stated purpose." |

## Recording

- **Silent scripted capture:** run `.venv/bin/python frontend/record_demo.py` with the server running. It writes `submission/media/terratwin_demo.webm` (65 s, 1280×800, made with headless Chrome and software rendering).
- **Final narrated video:** use a screen recorder (OBS Studio, or GNOME's Ctrl+Shift+Alt+R) at 1920×1080 in a full-screen browser, then follow the table above. If imagery is slow, use **Local studies → Saved examples**; they are labeled as saved and must be described that way.
- Check the official length and format limits before final editing (see [CHALLENGE_MAPPING.md](CHALLENGE_MAPPING.md)).
