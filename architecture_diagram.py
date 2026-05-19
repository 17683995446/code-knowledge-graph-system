"""
System Architecture Visualization Module
Generates SVG diagrams for the code knowledge graph system architecture.
"""

import os


def generate_system_architecture_svg():
    """Generate system architecture diagram in SVG format."""
    svg_content = '''<svg width="100%" viewBox="0 0 680 520">
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</marker>
</defs>

<!-- Title -->
<text x="340" y="30" text-anchor="middle" class="th" style="font-size:16px;font-weight:600;">System Architecture</text>

<!-- Layer 1: Code File Changes -->
<g class="c-coral">
<rect x="40" y="50" width="120" height="50" rx="8" class="box"/>
<text x="100" y="75" text-anchor="middle" class="t" dominant-baseline="central">Code File Changes</text>
</g>

<!-- Arrow 1 -->
<line x1="160" y1="75" x2="200" y2="75" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Layer 2: Cross-Platform File Monitor -->
<g class="c-amber">
<rect x="200" y="50" width="140" height="50" rx="8" class="box"/>
<text x="270" y="75" text-anchor="middle" class="t" dominant-baseline="central">File Monitor</text>
</g>

<!-- Arrow 2 -->
<line x1="340" y1="75" x2="380" y2="75" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Layer 3: Debounce Merge Queue -->
<g class="c-lime">
<rect x="380" y="50" width="140" height="50" rx="8" class="box"/>
<text x="450" y="75" text-anchor="middle" class="t" dominant-baseline="central">Debounce Queue</text>
</g>

<!-- Arrow 3 -->
<line x1="520" y1="75" x2="560" y2="75" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Layer 4: Incremental Update Engine -->
<g class="c-mint">
<rect x="40" y="130" width="140" height="50" rx="8" class="box"/>
<text x="110" y="155" text-anchor="middle" class="t" dominant-baseline="central">Update Engine</text>
</g>

<!-- Arrow 4 -->
<line x1="180" y1="155" x2="220" y2="155" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Layer 5: SQLite Database -->
<g class="c-teal">
<rect x="220" y="130" width="120" height="50" rx="8" class="box"/>
<text x="280" y="155" text-anchor="middle" class="t" dominant-baseline="central">SQLite DB</text>
</g>

<!-- Arrow down to Parser Interface -->
<line x1="280" y1="180" x2="280" y2="210" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Layer 6: Universal Parser Interface -->
<g class="c-sky">
<rect x="200" y="210" width="160" height="40" rx="8" class="box"/>
<text x="280" y="230" text-anchor="middle" class="t" dominant-baseline="central">Parser Interface</text>
</g>

<!-- Arrows to Language Parsers -->
<line x1="200" y1="230" x2="140" y2="280" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="230" y1="250" x2="230" y2="280" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="280" y1="250" x2="320" y2="280" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="330" y1="250" x2="410" y2="280" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="360" y1="230" x2="500" y2="280" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Language Parsers -->
<g class="c-indigo">
<rect x="80" y="280" width="80" height="35" rx="6" class="box"/>
<text x="120" y="297" text-anchor="middle" class="ts" dominant-baseline="central">Python</text>
</g>

<g class="c-violet">
<rect x="190" y="280" width="80" height="35" rx="6" class="box"/>
<text x="230" y="297" text-anchor="middle" class="ts" dominant-baseline="central">Java</text>
</g>

<g class="c-magenta">
<rect x="300" y="280" width="80" height="35" rx="6" class="box"/>
<text x="340" y="297" text-anchor="middle" class="ts" dominant-baseline="central">JavaScript</text>
</g>

<g class="c-slate">
<rect x="410" y="280" width="80" height="35" rx="6" class="box"/>
<text x="450" y="297" text-anchor="middle" class="ts" dominant-baseline="central">ArkTS</text>
</g>

<g class="c-coral">
<rect x="520" y="280" width="80" height="35" rx="6" class="box"/>
<text x="560" y="297" text-anchor="middle" class="ts" dominant-baseline="central">Go</text>
</g>

<!-- More parsers row -->
<g class="c-amber">
<rect x="135" y="340" width="80" height="35" rx="6" class="box"/>
<text x="175" y="357" text-anchor="middle" class="ts" dominant-baseline="central">C/C++</text>
</g>

<g class="c-lime">
<rect x="245" y="340" width="80" height="35" rx="6" class="box"/>
<text x="285" y="357" text-anchor="middle" class="ts" dominant-baseline="central">Rust</text>
</g>

<g class="c-mint">
<rect x="355" y="340" width="80" height="35" rx="6" class="box"/>
<text x="395" y="357" text-anchor="middle" class="ts" dominant-baseline="central">TypeScript</text>
</g>

<g class="c-teal">
<rect x="465" y="340" width="80" height="35" rx="6" class="box"/>
<text x="505" y="357" text-anchor="middle" class="ts" dominant-baseline="central">...</text>
</g>

<!-- Arrows to more parsers -->
<line x1="120" y1="315" x2="175" y2="340" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="230" y1="315" x2="285" y2="340" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="340" y1="315" x2="395" y2="340" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<line x1="450" y1="315" x2="505" y2="340" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Web Visualization -->
<g class="c-sky">
<rect x="440" y="130" width="140" height="50" rx="8" class="box"/>
<text x="510" y="155" text-anchor="middle" class="t" dominant-baseline="central">Web Dashboard</text>
</g>

<!-- Arrow from DB to Web -->
<line x1="340" y1="155" x2="440" y2="155" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Legend -->
<text x="340" y="420" text-anchor="middle" class="ts" style="fill:#8A8A8A;">Language-agnostic design: One system, all languages</text>
<text x="340" y="445" text-anchor="middle" class="ts" style="fill:#8A8A8A;">First Principles: Atomic updates, incremental processing, 2s response</text>
<text x="340" y="470" text-anchor="middle" class="ts" style="fill:#8A8A8A;">Pluggable parsers: Tree-sitter + ArkAnalyzer + Custom</text>
<text x="340" y="495" text-anchor="middle" class="ts" style="fill:#8A8A8A;">Real-time visualization: Auto-refresh on file changes</text>
</svg>'''
    return svg_content


def generate_flowchart_svg():
    """Generate system flowchart diagram in SVG format."""
    svg_content = '''<svg width="100%" viewBox="0 0 680 600">
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</marker>
</defs>

<!-- Title -->
<text x="340" y="30" text-anchor="middle" class="th" style="font-size:16px;font-weight:600;">System Flowchart</text>

<!-- Start -->
<g class="c-mint">
<ellipse cx="340" cy="60" rx="50" ry="25" class="box"/>
<text x="340" y="60" text-anchor="middle" class="t" dominant-baseline="central">Start Service</text>
</g>

<!-- Arrow -->
<line x1="340" y1="85" x2="340" y2="110" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Initialize DB -->
<g class="c-sky">
<rect x="270" y="110" width="140" height="40" rx="8" class="box"/>
<text x="340" y="130" text-anchor="middle" class="t" dominant-baseline="central">Initialize Database</text>
</g>

<!-- Arrow -->
<line x1="340" y1="150" x2="340" y2="175" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Full Sync -->
<g class="c-amber">
<rect x="270" y="175" width="140" height="40" rx="8" class="box"/>
<text x="340" y="195" text-anchor="middle" class="t" dominant-baseline="central">Full Sync</text>
</g>

<!-- Arrow -->
<line x1="340" y1="215" x2="340" y2="240" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Start Monitor -->
<g class="c-lime">
<rect x="270" y="240" width="140" height="40" rx="8" class="box"/>
<text x="340" y="260" text-anchor="middle" class="t" dominant-baseline="central">Start File Monitor</text>
</g>

<!-- Arrow -->
<line x1="340" y1="280" x2="340" y2="305" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Event Loop (Diamond) -->
<g class="c-coral">
<polygon points="340,305 420,340 340,375 260,340" class="box"/>
<text x="340" y="340" text-anchor="middle" class="t" dominant-baseline="central">File Event?</text>
</g>

<!-- Arrow - No (Exit) -->
<line x1="260" y1="340" x2="180" y2="340" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<text x="220" y="330" text-anchor="middle" class="ts">No</text>

<!-- Exit -->
<g class="c-slate">
<ellipse cx="130" cy="340" rx="50" ry="25" class="box"/>
<text x="130" y="340" text-anchor="middle" class="t" dominant-baseline="central">Exit</text>
</g>

<!-- Arrow - Yes -->
<line x1="420" y1="340" x2="500" y2="340" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<text x="460" y="330" text-anchor="middle" class="ts">Yes</text>

<!-- Debounce -->
<g class="c-violet">
<rect x="500" y="320" width="140" height="40" rx="8" class="box"/>
<text x="570" y="340" text-anchor="middle" class="t" dominant-baseline="central">Debounce (1s)</text>
</g>

<!-- Arrow -->
<line x1="570" y1="360" x2="570" y2="390" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Identify Language -->
<g class="c-indigo">
<rect x="500" y="390" width="140" height="40" rx="8" class="box"/>
<text x="570" y="410" text-anchor="middle" class="t" dominant-baseline="central">Identify Language</text>
</g>

<!-- Arrow -->
<line x1="570" y1="430" x2="570" y2="455" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Parse File -->
<g class="c-teal">
<rect x="500" y="455" width="140" height="40" rx="8" class="box"/>
<text x="570" y="475" text-anchor="middle" class="t" dominant-baseline="central">Parse File</text>
</g>

<!-- Arrow -->
<line x1="570" y1="495" x2="570" y2="520" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>

<!-- Update DB -->
<g class="c-magenta">
<rect x="500" y="520" width="140" height="40" rx="8" class="box"/>
<text x="570" y="540" text-anchor="middle" class="t" dominant-baseline="central">Update Database</text>
</g>

<!-- Arrow back to loop -->
<path d="M 500 540 Q 340 540 340 450 Q 340 375 300 340" fill="none" stroke="#8A8A8A" marker-end="url(#arrow)"/>

<!-- Left side: Full Sync Detail -->
<g class="c-slate" opacity="0.7">
<rect x="40" y="400" width="180" height="150" rx="8" fill="#F2F2F2" stroke="#BABABA"/>
<text x="130" y="425" text-anchor="middle" class="th">Full Sync Detail</text>

<rect x="55" y="440" width="150" height="25" rx="4" fill="white" stroke="#D6D6D6"/>
<text x="130" y="452" text-anchor="middle" class="ts">Scan all files</text>

<rect x="55" y="470" width="150" height="25" rx="4" fill="white" stroke="#D6D6D6"/>
<text x="130" y="482" text-anchor="middle" class="ts">Calculate MD5 hash</text>

<rect x="55" y="500" width="150" height="25" rx="4" fill="white" stroke="#D6D6D6"/>
<text x="130" y="512" text-anchor="middle" class="ts">Compare with DB</text>

<rect x="55" y="530" width="150" height="25" rx="4" fill="white" stroke="#D6D6D6"/>
<text x="130" y="542" text-anchor="middle" class="ts">Batch process</text>
</g>

<!-- Arrow from Full Sync to Detail -->
<line x1="270" y1="195" x2="220" y2="400" class="leader" stroke="#BABABA" stroke-dasharray="4"/>

</svg>'''
    return svg_content


def generate_sequence_diagram_svg():
    """Generate system sequence diagram in SVG format."""
    svg_content = '''<svg width="100%" viewBox="0 0 680 550">
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</marker>
</defs>

<!-- Title -->
<text x="340" y="30" text-anchor="middle" class="th" style="font-size:16px;font-weight:600;">Sequence Diagram: File Change Processing</text>

<!-- Actors/Lifelines -->
<g>
<!-- File System -->
<rect x="50" y="50" width="80" height="30" rx="4" fill="#FCA18D" stroke="#D33A17"/>
<text x="90" y="70" text-anchor="middle" class="t" dominant-baseline="central">FileSystem</text>
<line x1="90" y1="80" x2="90" y2="500" stroke="#D6D6D6" stroke-dasharray="4"/>

<!-- File Monitor -->
<rect x="180" y="50" width="80" height="30" rx="4" fill="#F8C982" stroke="#B17110"/>
<text x="220" y="70" text-anchor="middle" class="t" dominant-baseline="central">Monitor</text>
<line x1="220" y1="80" x2="220" y2="500" stroke="#D6D6D6" stroke-dasharray="4"/>

<!-- Debounce Queue -->
<rect x="310" y="50" width="80" height="30" rx="4" fill="#BCF362" stroke="#639B08"/>
<text x="350" y="70" text-anchor="middle" class="t" dominant-baseline="central">Queue</text>
<line x1="350" y1="80" x2="350" y2="500" stroke="#D6D6D6" stroke-dasharray="4"/>

<!-- Update Engine -->
<rect x="440" y="50" width="80" height="30" rx="4" fill="#76F4C0" stroke="#0EA466"/>
<text x="480" y="70" text-anchor="middle" class="t" dominant-baseline="central">Engine</text>
<line x1="480" y1="80" x2="480" y2="500" stroke="#D6D6D6" stroke-dasharray="4"/>

<!-- Database -->
<rect x="570" y="50" width="80" height="30" rx="4" fill="#78F2F2" stroke="#11A2A2"/>
<text x="610" y="70" text-anchor="middle" class="t" dominant-baseline="central">SQLite</text>
<line x1="610" y1="80" x2="610" y2="500" stroke="#D6D6D6" stroke-dasharray="4"/>
</g>

<!-- Messages -->
<g>
<!-- 1. File Modified -->
<line x1="90" y1="100" x2="220" y2="100" class="arr" marker-end="url(#arrow)" stroke="#474747"/>
<text x="155" y="95" text-anchor="middle" class="ts">1: file_modified</text>

<!-- 2. Queue Event -->
<line x1="220" y1="130" x2="350" y2="130" class="arr" marker-end="url(#arrow)" stroke="#474747"/>
<text x="285" y="125" text-anchor="middle" class="ts">2: queue_event</text>

<!-- 3. Wait Debounce -->
<rect x="330" y="145" width="40" height="20" rx="3" fill="#E3FDB9" stroke="#639B08"/>
<text x="350" y="155" text-anchor="middle" class="ts">wait 1s</text>

<!-- 4. Process Event -->
<line x1="350" y1="180" x2="480" y2="180" class="arr" marker-end="url(#arrow)" stroke="#474747"/>
<text x="415" y="175" text-anchor="middle" class="ts">3: process_event</text>

<!-- 5. Delete Old Data -->
<line x1="480" y1="210" x2="610" y2="210" class="arr" marker-end="url(#arrow)" stroke="#474747"/>
<text x="545" y="205" text-anchor="middle" class="ts">4: DELETE old</text>

<!-- 6. Parse File -->
<line x1="480" y1="240" x2="350" y2="240" class="arr" marker-end="url(#arrow)" stroke="#474747" stroke-dasharray="4"/>
<text x="415" y="235" text-anchor="middle" class="ts">5: parse_file</text>

<!-- 7. Return AST -->
<line x1="350" y1="270" x2="480" y2="270" class="arr" marker-end="url(#arrow)" stroke="#474747" stroke-dasharray="4"/>
<text x="415" y="265" text-anchor="middle" class="ts">6: return AST</text>

<!-- 8. Insert New Data -->
<line x1="480" y1="300" x2="610" y2="300" class="arr" marker-end="url(#arrow)" stroke="#474747"/>
<text x="545" y="295" text-anchor="middle" class="ts">7: INSERT new</text>

<!-- 9. Commit -->
<line x1="480" y1="330" x2="610" y2="330" class="arr" marker-end="url(#arrow)" stroke="#474747"/>
<text x="545" y="325" text-anchor="middle" class="ts">8: COMMIT</text>

<!-- 10. Notify Web -->
<line x1="480" y1="360" x2="220" y2="360" class="arr" marker-end="url(#arrow)" stroke="#474747" stroke-dasharray="4"/>
<text x="350" y="355" text-anchor="middle" class="ts">9: notify_update</text>

<!-- 11. Refresh UI -->
<line x1="220" y1="390" x2="90" y2="390" class="arr" marker-end="url(#arrow)" stroke="#474747" stroke-dasharray="4"/>
<text x="155" y="385" text-anchor="middle" class="ts">10: refresh_ui</text>
</g>

<!-- Notes -->
<g>
<rect x="40" y="420" width="280" height="70" rx="6" fill="#FED2C7" stroke="#D33A17" opacity="0.5"/>
<text x="50" y="445" class="ts">Note: All operations within single transaction</text>
<text x="50" y="465" class="ts">Delete-then-insert ensures consistency</text>
<text x="50" y="485" class="ts">Total time: &lt; 2 seconds</text>
</g>

</svg>'''
    return svg_content


def generate_data_model_svg():
    """Generate database schema diagram in SVG format."""
    svg_content = '''<svg width="100%" viewBox="0 0 680 520">
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</marker>
</defs>

<!-- Title -->
<text x="340" y="30" text-anchor="middle" class="th" style="font-size:16px;font-weight:600;">Database Schema</text>

<!-- files table -->
<g class="c-sky">
<rect x="40" y="50" width="180" height="140" rx="8" class="box"/>
<text x="130" y="75" text-anchor="middle" class="th">files</text>
<line x1="50" y1="85" x2="210" y2="85" stroke="#0B7BC1" stroke-width="1"/>
<text x="55" y="105" class="ts" style="font-family:monospace;">id INTEGER PK</text>
<text x="55" y="125" class="ts" style="font-family:monospace;">path TEXT UNIQUE</text>
<text x="55" y="145" class="ts" style="font-family:monospace;">language TEXT</text>
<text x="55" y="165" class="ts" style="font-family:monospace;">hash BLOB</text>
<text x="55" y="185" class="ts" style="font-family:monospace;">modified INTEGER</text>
</g>

<!-- types table -->
<g class="c-mint">
<rect x="250" y="50" width="180" height="130" rx="8" class="box"/>
<text x="340" y="75" text-anchor="middle" class="th">types</text>
<line x1="260" y1="85" x2="420" y2="85" stroke="#0EA466" stroke-width="1"/>
<text x="265" y="105" class="ts" style="font-family:monospace;">id INTEGER PK</text>
<text x="265" y="125" class="ts" style="font-family:monospace;">name TEXT</text>
<text x="265" y="145" class="ts" style="font-family:monospace;">file_id INTEGER FK</text>
<text x="265" y="165" class="ts" style="font-family:monospace;">kind TEXT</text>
</g>

<!-- functions table -->
<g class="c-amber">
<rect x="460" y="50" width="180" height="110" rx="8" class="box"/>
<text x="550" y="75" text-anchor="middle" class="th">functions</text>
<line x1="470" y1="85" x2="630" y2="85" stroke="#B17110" stroke-width="1"/>
<text x="475" y="105" class="ts" style="font-family:monospace;">id INTEGER PK</text>
<text x="475" y="125" class="ts" style="font-family:monospace;">name TEXT</text>
<text x="475" y="145" class="ts" style="font-family:monospace;">type_id INTEGER FK</text>
</g>

<!-- calls table -->
<g class="c-coral">
<rect x="40" y="220" width="180" height="90" rx="8" class="box"/>
<text x="130" y="245" text-anchor="middle" class="th">calls</text>
<line x1="50" y1="255" x2="210" y2="255" stroke="#D33A17" stroke-width="1"/>
<text x="55" y="275" class="ts" style="font-family:monospace;">caller_id INTEGER</text>
<text x="55" y="295" class="ts" style="font-family:monospace;">callee_id INTEGER</text>
</g>

<!-- references table -->
<g class="c-violet">
<rect x="250" y="220" width="180" height="100" rx="8" class="box"/>
<text x="340" y="245" text-anchor="middle" class="th">references</text>
<line x1="260" y1="255" x2="420" y2="255" stroke="#9019E6" stroke-width="1"/>
<text x="265" y="275" class="ts" style="font-family:monospace;">from_id INTEGER</text>
<text x="265" y="295" class="ts" style="font-family:monospace;">to_id INTEGER</text>
<text x="265" y="315" class="ts" style="font-family:monospace;">kind TEXT</text>
</g>

<!-- Relationships -->
<g>
<!-- files -> types -->
<line x1="220" y1="120" x2="250" y2="120" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<text x="235" y="110" text-anchor="middle" class="ts">1:N</text>

<!-- types -> functions -->
<line x1="430" y1="120" x2="460" y2="120" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<text x="445" y="110" text-anchor="middle" class="ts">1:N</text>

<!-- functions -> calls (caller) -->
<path d="M 550 160 Q 550 200 220 200 Q 130 200 130 220" fill="none" stroke="#8A8A8A" marker-end="url(#arrow)"/>
<text x="380" y="195" text-anchor="middle" class="ts">caller</text>

<!-- functions -> calls (callee) -->
<path d="M 550 160 Q 550 190 250 190 Q 160 190 160 220" fill="none" stroke="#8A8A8A" marker-end="url(#arrow)"/>
<text x="350" y="185" text-anchor="middle" class="ts">callee</text>

<!-- types -> references -->
<line x1="340" y1="180" x2="340" y2="220" class="arr" marker-end="url(#arrow)" stroke="#8A8A8A"/>
<text x="355" y="205" text-anchor="middle" class="ts">from/to</text>
</g>

<!-- Design Notes -->
<g>
<rect x="40" y="350" width="600" height="150" rx="8" fill="#F2F2F2" stroke="#BABABA"/>
<text x="340" y="375" text-anchor="middle" class="th">Design Principles</text>

<text x="60" y="405" class="ts">• Integer Primary Keys: Maximum performance, minimal storage</text>
<text x="60" y="430" class="ts">• Foreign Key Relationships: Maintain referential integrity</text>
<text x="60" y="455" class="ts">• Composite Unique Constraints: Prevent duplicate entries</text>
<text x="60" y="480" class="ts">• Generic Schema: Same tables support all programming languages</text>
<text x="60" y="505" class="ts">• Kind Field: Distinguish between class/interface/struct/enum/function</text>
</g>

</svg>'''
    return svg_content


def generate_performance_chart_svg():
    """Generate performance metrics chart in SVG format."""
    svg_content = '''<svg width="100%" viewBox="0 0 680 450">
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</marker>
</defs>

<!-- Title -->
<text x="340" y="30" text-anchor="middle" class="th" style="font-size:16px;font-weight:600;">Performance Metrics</text>

<!-- Chart Background -->
<rect x="80" y="60" width="520" height="280" rx="8" fill="#FAFAFA" stroke="#D6D6D6"/>

<!-- Y-axis labels -->
<text x="70" y="70" text-anchor="end" class="ts">Time (s)</text>
<text x="70" y="100" text-anchor="end" class="ts">80</text>
<text x="70" y="150" text-anchor="end" class="ts">60</text>
<text x="70" y="200" text-anchor="end" class="ts">40</text>
<text x="70" y="250" text-anchor="end" class="ts">20</text>
<text x="70" y="300" text-anchor="end" class="ts">0</text>

<!-- Grid lines -->
<line x1="80" y1="100" x2="600" y2="100" stroke="#E3E3E3" stroke-dasharray="2"/>
<line x1="80" y1="150" x2="600" y2="150" stroke="#E3E3E3" stroke-dasharray="2"/>
<line x1="80" y1="200" x2="600" y2="200" stroke="#E3E3E3" stroke-dasharray="2"/>
<line x1="80" y1="250" x2="600" y2="250" stroke="#E3E3E3" stroke-dasharray="2"/>

<!-- X-axis labels -->
<text x="160" y="330" text-anchor="middle" class="ts">100K lines</text>
<text x="340" y="330" text-anchor="middle" class="ts">1M lines</text>
<text x="520" y="330" text-anchor="middle" class="ts">10M lines</text>

<!-- Bars -->
<!-- Full Sync Time -->
<rect x="130" y="295" width="40" height="5" fill="#FCA18D"/>
<rect x="310" y="240" width="40" height="60" fill="#FCA18D"/>
<rect x="490" y="100" width="40" height="200" fill="#FCA18D"/>

<!-- Single File Update Time -->
<rect x="175" y="298" width="40" height="2" fill="#76F4C0"/>
<rect x="355" y="294" width="40" height="6" fill="#76F4C0"/>
<rect x="535" y="280" width="40" height="20" fill="#76F4C0"/>

<!-- Legend -->
<rect x="150" y="360" width="20" height="15" fill="#FCA18D"/>
<text x="180" y="372" class="ts">Full Sync Time</text>

<rect x="320" y="360" width="20" height="15" fill="#76F4C0"/>
<text x="350" y="372" class="ts">Single File Update</text>

<!-- Data Table -->
<rect x="80" y="400" width="520" height="40" rx="4" fill="#F2F2F2" stroke="#D6D6D6"/>
<text x="160" y="415" text-anchor="middle" class="ts">Code Size</text>
<text x="340" y="415" text-anchor="middle" class="ts">Full Sync</text>
<text x="520" y="415" text-anchor="middle" class="ts">Single Update</text>

<text x="160" y="432" text-anchor="middle" class="ts">100K / 1M / 10M</text>
<text x="340" y="432" text-anchor="middle" class="ts">30s / 8min / 70min</text>
<text x="520" y="432" text-anchor="middle" class="ts">&lt;0.3s / &lt;0.8s / &lt;2s</text>

</svg>'''
    return svg_content


def save_all_diagrams(output_directory):
    """Save all diagram SVGs to the specified directory."""
    os.makedirs(output_directory, exist_ok=True)
    
    diagrams = {
        'system_architecture.svg': generate_system_architecture_svg(),
        'system_flowchart.svg': generate_flowchart_svg(),
        'sequence_diagram.svg': generate_sequence_diagram_svg(),
        'database_schema.svg': generate_data_model_svg(),
        'performance_metrics.svg': generate_performance_chart_svg()
    }
    
    for filename, content in diagrams.items():
        filepath = os.path.join(output_directory, filename)
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(content)
    
    return list(diagrams.keys())


if __name__ == '__main__':
    diagrams_dir = '/data/user/work/code_knowledge_graph_system/static/diagrams'
    saved_files = save_all_diagrams(diagrams_dir)
    print(f"Generated {len(saved_files)} diagrams:")
    for filename in saved_files:
        print(f"  - {filename}")
