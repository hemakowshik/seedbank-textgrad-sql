// Builds the IEEE-style paper for SeedSQL v2 (two-column, US Letter, Times New Roman).
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType, WidthType,
  BorderStyle, ShadingType, SectionType, TabStopType, VerticalAlign, LineRuleType,
} = require("docx");

const FONT = "Times New Roman";
const COL = 5040;            // one column, DXA (3.5 in)
const PT = (n) => n * 2;     // half-points

// ---------- inline markup: **bold**, *italic*, _{sub}, ^{sup}, `code`
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\}|`[^`]+`)/g;
  let last = 0, m;
  const push = (t, extra = {}) => { if (t) out.push(new TextRun({ text: t, font: FONT, size: base.size || PT(10), ...base, ...extra })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith("*")) push(tok.slice(1, -1), { italics: true });
    else if (tok.startsWith("_{")) push(tok.slice(2, -1), { subScript: true, italics: base.italics });
    else if (tok.startsWith("^{")) push(tok.slice(2, -1), { superScript: true });
    else push(tok.slice(1, -1), { font: "Courier New", size: PT(8.5) });
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return out;
}

const P = (text, opt = {}) => new Paragraph({
  children: runs(text, opt.run || {}),
  alignment: opt.align || AlignmentType.JUSTIFIED,
  indent: opt.noIndent ? undefined : { firstLine: 202 },
  spacing: { before: 0, after: opt.after || 0, line: 240 },
  keepNext: opt.keepNext,
});
const P0 = (text, opt = {}) => P(text, { ...opt, noIndent: true });

let h1n = 0, h2n = 0;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
const H1 = (t) => { h2n = 0; return new Paragraph({
  children: [new TextRun({ text: `${ROMAN[h1n++]}. ${t}`, font: FONT, size: PT(10), smallCaps: true })],
  alignment: AlignmentType.CENTER, spacing: { before: 200, after: 100 }, keepNext: true, keepLines: true }); };
const H2 = (t) => new Paragraph({
  children: [new TextRun({ text: `${String.fromCharCode(65 + h2n++)}. ${t}`, font: FONT, size: PT(10), italics: true })],
  spacing: { before: 100, after: 60 }, keepNext: true, keepLines: true });

// bullet-like paragraph with hanging indent, label given explicitly (no literal bullet glyphs)
const Item = (label, text) => new Paragraph({
  children: [new TextRun({ text: label + "\t", font: FONT, size: PT(10) }), ...runs(text)],
  alignment: AlignmentType.JUSTIFIED, indent: { left: 288, hanging: 288 },
  tabStops: [{ type: TabStopType.LEFT, position: 288 }], spacing: { before: 0, after: 30 } });

// display equation with right-aligned number
const EQ = (parts, num) => new Paragraph({
  children: [new TextRun({ text: "\t", font: FONT }), ...runs(parts, { italics: false }),
             new TextRun({ text: `\t(${num})`, font: FONT, size: PT(10) })],
  tabStops: [{ type: TabStopType.CENTER, position: COL / 2 }, { type: TabStopType.RIGHT, position: COL }],
  spacing: { before: 80, after: 80 } });

// SQL / code block
const CODE = (lines) => lines.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l, font: "Courier New", size: PT(7.5) })],
  shading: { type: ShadingType.CLEAR, color: "auto", fill: "F2F2F2" },
  spacing: { before: i === 0 ? 60 : 0, after: i === lines.length - 1 ? 60 : 0, line: 220, lineRule: LineRuleType.AUTO },
  keepNext: i < lines.length - 1, indent: { left: 72, right: 72 } }));

const caption = (text, above = true) => new Paragraph({
  children: runs(text, { size: PT(8) }), alignment: AlignmentType.CENTER,
  spacing: { before: above ? 120 : 40, after: above ? 60 : 140 }, keepNext: above });
const tcaption = (num, text) => [
  new Paragraph({ children: [new TextRun({ text: `TABLE ${num}`, font: FONT, size: PT(8) })], alignment: AlignmentType.CENTER, spacing: { before: 140, after: 0 }, keepNext: true }),
  new Paragraph({ children: [new TextRun({ text, font: FONT, size: PT(8), smallCaps: true })], alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60 }, keepNext: true }),
];

const thin = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function TABLE(widths, rows, opt = {}) {
  return [TABLE0(widths, rows, opt), new Paragraph({ children: [], spacing: { before: 0, after: 80, line: 120 } })];
}
function TABLE0(widths, rows, opt = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths, alignment: AlignmentType.CENTER,
    borders: { top: thin, bottom: thin, left: none, right: none, insideHorizontal: none, insideVertical: none },
    rows: rows.map((r, ri) => new TableRow({
      cantSplit: true, tableHeader: ri === 0,
      children: r.map((c, ci) => new TableCell({
        width: { size: widths[ci], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
        margins: { top: 20, bottom: 20, left: 50, right: 50 },
        borders: ri === 0 ? { bottom: thin, top: thin, left: none, right: none } : { top: none, bottom: ri === rows.length - 1 ? thin : none, left: none, right: none },
        shading: opt.highlight && opt.highlight(ri) ? { type: ShadingType.CLEAR, color: "auto", fill: "EEF3EE" } : undefined,
        children: [new Paragraph({
          children: runs(String(c), { size: PT(opt.size || 7.5), bold: ri === 0 }),
          alignment: (opt.align && opt.align[ci]) || (ci === 0 ? AlignmentType.LEFT : AlignmentType.CENTER),
          keepNext: ri < rows.length - 1, spacing: { before: 0, after: 0, line: 220 } })],
      })),
    })),
  });
}

const IMG = (file, wpx, hpx) => new Paragraph({
  children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: wpx, height: hpx },
    altText: { title: file, description: file, name: file } })],
  alignment: AlignmentType.CENTER, spacing: { before: 120, after: 0 }, keepNext: true });

// ====================================================================== content
const title = [
  new Paragraph({ children: [new TextRun({ text: "Validation-Guided TextGrad for Seed-Bank Text-to-SQL: Catching Queries That Run but Give the Wrong Answer", font: FONT, size: PT(22) })],
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 200 } }),
  new Paragraph({ children: [new TextRun({ text: "Gayathri Priya V, Gonu Guntla Hema Kowshik, Bhavin G Kamat", font: FONT, size: PT(11) })], alignment: AlignmentType.CENTER, spacing: { after: 40 } }),
  new Paragraph({ children: [new TextRun({ text: "Department of Computer Science and Engineering (AI & ML), PES University, Bengaluru, India", font: FONT, size: PT(10), italics: true })], alignment: AlignmentType.CENTER, spacing: { after: 40 } }),
  new Paragraph({ children: [new TextRun({ text: "Guide: [guide name, designation]   ·   Emails: [author e-mail addresses]", font: FONT, size: PT(9), highlight: "yellow" })], alignment: AlignmentType.CENTER, spacing: { after: 240 } }),
];

const B = []; // body
const add = (...xs) => xs.flat().forEach((x) => B.push(x));

add(new Paragraph({ children: [new TextRun({ text: "Abstract", font: FONT, size: PT(9), bold: true, italics: true }), new TextRun({ text: "—", font: FONT, size: PT(9), bold: true }),
  ...runs("Seed-bank staff ask questions such as “which lots have a most recent germination rate below 75%?”. Large language models (LLMs) can turn such questions into SQL, but the most damaging errors are queries that run without error and still return the wrong rows, for example by using every germination test instead of each lot’s latest one. Execution feedback cannot see these errors, and the correct answer is unknown at inference time. We present SeedSQL, which extends TextGrad prompt optimization with a gold-free validator. The validator reads the question’s intent with deterministic rules, checks the SQL against 13 configurable domain and temporal rules, and runs metamorphic tests: it changes an in-memory copy of the database in a controlled way (for example, adds a newer passing test for a returned lot) and checks that the query’s answer changes as the question demands. Its findings ground the TextGrad loss, veto a premature PASS, and are turned into typed textual gradients tagged with rule identifiers. We also build a 60-question benchmark over 66 real ICRISAT genebank accessions from Genesys with simulated monitoring records, and introduce temporal robust accuracy, which counts a query as correct only if it also matches the gold answer on five changed database states. Offline, the validator raised no false alarms on the 60 gold queries or on 18 correct rewrites, and flagged all 105 injected wrong-but-running mistakes; these are development-set figures. Five injected mistakes returned exactly the gold answer on the benchmark database but diverged on changed states, which ordinary execution accuracy would score as correct. The LLM comparison of seven methods is specified and implemented; its results will be added after the runs.", { size: PT(9), bold: true })],
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 80 } }));
add(new Paragraph({ children: [new TextRun({ text: "Index Terms", font: FONT, size: PT(9), bold: true, italics: true }), new TextRun({ text: "—Text-to-SQL, large language models, TextGrad, prompt optimization, metamorphic testing, semantic validation, genebanks, seed banks.", font: FONT, size: PT(9), bold: true })],
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 120 } }));

// I
add(H1("Introduction: Why Seed-Bank Questions Break Text-to-SQL"));
add(H2("The Problem: Queries That Run but Answer Wrongly"));
add(P("Seed banks keep each seed lot under watch for years. They record where it is stored, how much is left, the temperature and humidity of the store, every germination test, and every distribution to farmers. Coordinators need answers that combine these records: which lots need retesting, which drought-tolerant varieties still have viable stock, which stores keep seeds outside recommended conditions. Most coordinators do not write SQL."));
add(P("LLM-based Text-to-SQL can bridge this gap [1]. Its errors come in two kinds. *Execution errors*, such as a misspelled column, are easy to see because the database rejects the query, and execution-guided self-correction fixes many of them [5]–[7]. *Semantic errors* are harder: the query runs and returns plausible rows, but it answers a different question. Seed-bank questions invite exactly these errors because their meaning is temporal and per entity. “Most recent germination rate” means the latest test *of each lot*, not every test and not the newest test in the whole table. “Viable stock” means stock above zero *and* a passing latest test. In deployment there is no reference answer to compare against, so neither execution feedback nor a generic LLM judge has a reliable signal."));
add(H2("Our Idea in One Paragraph"));
add(P("TextGrad [11] improves a variable, here the generator’s instructions, by asking an LLM to criticise the output (a textual *loss*), turning the criticism into advice aimed at the variable (a textual *gradient*), and rewriting the variable (a *step*). We keep this loop but ground the loss in evidence that needs no gold answer. A deterministic validator first extracts what the question requires, for example “latest test per lot, threshold below 75%”. It then checks the SQL with domain rules and runs *metamorphic tests* [13], [14]: if a returned lot receives a newer test of 90%, a correct answer to “lots whose latest rate is below 75%” must drop that lot. If the query still returns it, the query ignores the latest-test logic. The findings are given to the evaluator, block a PASS, and become typed gradient bullets such as “[TEMP-LATEST] select the latest test separately for each lot”."));
add(H2("Contributions"));
add(Item("1)", "**Validation-guided TextGrad (VG-TextGrad):** a TextGrad loop whose loss is grounded in gold-free validator evidence, with a validator veto on PASS, typed gradients tagged by rule, and an intent-conditioned rule memory for prompt-level optimization (Section V)."));
add(Item("2)", "**Intent-conditioned metamorphic tests for SQL:** six metamorphic relations, selected from the question’s intent, that test a query by controlled changes to an in-memory copy of the database (Section V-E)."));
add(Item("3)", "**A genebank-grounded benchmark:** a five-table SQLite database built from 66 real ICRISAT accessions published on Genesys [18], with simulated lots and monitoring records, and 60 questions with hand-written gold SQL in five categories and three tiers (Sections III–IV)."));
add(Item("4)", "**Temporal robust accuracy (TRA):** a stricter metric that re-checks every answer on five changed database states, and an offline evaluation of the validator by mutation testing [17] (Sections VI–VII)."));
add(Item("5)", "**An open implementation:** a read-only execution sandbox, an experiment runner with seven methods and paired statistics, and a browser interface that shows every refinement step."));
add(P("We do not claim that TextGrad, execution-guided refinement or metamorphic testing is new. The contribution is combining them so that a prompt optimizer receives a semantic signal that does not depend on the answer key, in a domain where such errors are common."));

// II
add(H1("Related Work: What Exists and What Is Missing"));
add(H2("LLM Text-to-SQL and How It Is Scored"));
add(P("A recent survey [1] describes LLM-based Text-to-SQL as generating executable SQL from a question and a schema. Spider [2] and BIRD [3] established *execution accuracy*: a prediction is judged by its result, not its text. Nan et al. [4] showed that prompt design, such as schema format and demonstration choice, changes accuracy substantially, which motivates our zero-shot and few-shot baselines. Zhong et al. [16] observed that one database can make a wrong query look right, and proposed evaluating on a distilled suite of databases; our temporal robust accuracy applies the same idea with domain-specific state changes."));
add(H2("Fixing Queries with Execution Feedback"));
add(P("MAC-SQL [5] refines queries with execution feedback inside a multi-agent framework; DART-SQL [6] combines question rewriting with execution-guided refinement; LitE-SQL [7] categorises execution errors and measures them before and after self-correction. Reflect-SQL [8] uses an LLM judge in feedback loops, and ZAS-SQL [9] distils rules from repeated zero-shot failures. These methods react mainly to errors the database or an LLM judge can see. Our validator targets errors that execute cleanly."));
add(H2("Optimizing Prompts with Textual Gradients"));
add(P("ProTeGi [10] optimises prompts with natural-language “gradients” and beam search. TextGrad [11] generalises this into automatic differentiation via text. Gurajada et al. [12] studied prompt optimization for production NL2SQL systems. In these methods the loss is written by an LLM from the task output; when the LLM cannot see a semantic error, the gradient cannot fix it. We supply that missing evidence."));
add(H2("Testing Without a Known Answer"));
add(P("Metamorphic testing [13], [14] checks software when the correct output is unknown, by checking a relation between outputs on related inputs. Rigger and Su [15] used this idea to find bugs in database engines. Mutation testing [17] measures a checker by injecting realistic faults and counting how many it detects. We use metamorphic relations to check *generated queries* rather than engines, and mutation testing to measure the validator."));
add(H2("Genebank Information Systems"));
add(P("Genebanks document accessions with standard passport descriptors and publish them through Genesys [18]; systems such as GRIN-Global [19] manage inventory and viability tests. Hay et al. [20] found inconsistencies in CGIAR genebank viability data, and the FAO Genebank Standards [21] set expectations for storage and monitoring. AgriWorld [22] studies code-executing LLM agents for verifiable agricultural reasoning. We found no prior work on validator-grounded textual-gradient optimization for querying genebank records."));

// III
add(H1("Data: Real Genesys Accessions with Simulated Monitoring Records"));
add(H2("Where the Accessions Come From"));
add(P("We downloaded the accession list of ICRISAT (FAO WIEWS code IND002) from Genesys [18]: 149,034 accession records, of which 148,933 carry a Genesys DOI. ICRISAT accession numbers carry crop prefixes (IS for sorghum, IP for pearl millet, ICC for chickpea, ICG for groundnut, ICP for pigeon pea, IE for finger millet, ISe for foxtail millet, and so on for 11 crops), which we use to assign the crop. With a fixed random seed (2026) we sample 6 accessions per crop, giving 66 accessions. Each row of the `SeedVariety` table keeps the real accession number, the holding genebank and the Genesys DOI, so every variety can be traced to its public record."));
add(H2("The Five Tables"));
add(P("Table I lists the tables. Lots, tests, readings and distributions link to their parent by `lot_id` or `variety_id`; `SeedLot.quantity` is the stock that remains after all distributions."));
add(tcaption("I", "Database Tables and Row Counts"));
add(TABLE([1250, 2990, 800], [
  ["Table", "Key columns (what one row means)", "Rows"],
  ["SeedVariety", "one real accession: crop, accession number, DOI, crop type, drought tolerance", "66"],
  ["SeedLot", "one stored lot: store, current quantity (g), regeneration date", "122"],
  ["GerminationTest", "one test of one lot: date, germination rate (%)", "294"],
  ["StorageLog", "one monthly reading: temperature (°C), humidity (%)", "4,004"],
  ["Distribution", "seed given to a farmer group: quantity (g), date", "152"],
], { align: [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.CENTER] }));

add(H2("What Is Simulated and Why"));
add(P("Genebanks do not publish per-lot monitoring data, so seed lots, germination tests, storage readings and distributions are simulated with the same fixed seed. Each accession has one to three lots in one of five stores. A lot’s germination falls from a starting value of 88–97% at a speed set by the store’s quality (cold rooms slowest, an ambient shelf fastest), plus noise, and is clipped to 18–99%. Storage readings are monthly; each lot’s series starts between mid-2022 and late 2025 and runs to the reference date, 1 November 2026. Crop type and drought tolerance follow a crop-level rule (millets and sorghum High; pulses and groundnut Medium), and the thresholds of 75% germination, 15 °C and 50% relative humidity are documented project assumptions, not agronomic recommendations. We therefore describe the database as *real accessions with simulated monitoring records*, not as real genebank operations data."));
// IV
add(H1("Benchmark: 60 Questions with Hand-Written Gold SQL"));
add(H2("Five Question Categories and Three Difficulty Tiers"));
add(P("We wrote 60 questions that a seed-bank coordinator would ask, each with a gold SQL query that we checked by hand. Each question has a category, given by the kind of reasoning it needs, and a tier, given by its complexity: roughly, Tier 1 needs one table and simple filters, Tier 2 adds grouping or one join, and Tier 3 adds several joins, per-lot temporal logic or combined conditions (Table II). The builder checks that every gold query returns a non-empty, tie-free answer, so that “top 5” questions have exactly one correct answer."));
add(tcaption("II", "Benchmark Questions by Category and Tier"));
add(TABLE([2000, 760, 760, 760, 760], [
  ["Category (example)", "Tier 1", "Tier 2", "Tier 3", "Total"],
  ["Temporal (latest test, date ranges)", "1", "4", "12", "17"],
  ["Domain (viable stock, storage limits)", "1", "5", "8", "14"],
  ["Aggregation (totals, averages)", "2", "7", "3", "12"],
  ["Join (lots with varieties)", "0", "5", "6", "11"],
  ["Retrieval (simple lookup)", "6", "0", "0", "6"],
  ["**Total**", "**10**", "**21**", "**29**", "**60**"],
]));
add(P("A typical Tier-3 temporal question is T3-01: “Which seed lots have a most recent germination rate below 75% and need retesting? Show the lot and that latest rate.” Its gold query selects, for each lot, the test whose date equals that lot’s maximum test date, and then applies the threshold (Section VIII)."));
add(H2("Domain Assumptions Written Down"));
add(P("The benchmark file states every assumption that changes an answer: the reference date (2026-11-01), the 75% germination threshold, the storage limits, the definition of viable stock (quantity above zero and latest rate at least 75%), and that `quantity` is already net of distributions. The same text is part of the schema description given to every method, so no method is judged on knowledge it was not given."));
add(H2("Keeping Examples Apart from Test Questions"));
add(P("The few-shot baseline uses four demonstrations. An automated test checks that no demonstration has the same SQL as, or a closely similar question to, any benchmark question (word-overlap Jaccard below 0.6). This check found that an earlier demonstration was a paraphrase of question TMP-01; we replaced it with a latest-storage-temperature example that teaches the same pattern on a different table."));

// V
add(H1("Method: How Validation-Guided TextGrad Works"));
add(H2("Problem Setup in Symbols"));
add(P("Let *D* be the database with schema description *S*, and *q* a question. The generator LLM *G*, given instructions *p* (the system prompt), returns a query, and the read-only executor *E* returns rows or an error:"));
add(EQ("*ŷ* = *G*(*p*, *S*, *q*),      *r* = *E*(*ŷ*, *D*)", 1));
add(P0("For evaluation only, each question has a gold query *y*^{∗} with result *R*^{∗} = *E*(*y*^{∗}, *D*). Refinement never sees *y*^{∗} or *R*^{∗}."));
add(H2("Baseline: The TextGrad Loop"));
add(P("TextGrad treats *p* as the trainable variable. At iteration *k* an evaluator LLM *L* writes a loss from what it can observe, a gradient LLM Γ turns it into advice for *p*, and a step LLM rewrites *p*:"));
add(EQ("ℓ_{k} = *L*(*q*, *S*, *ŷ*_{k}, *r*_{k}),    ∇_{p}ℓ_{k} = Γ(*p*_{k}, *q*, *ŷ*_{k}, *r*_{k}, ℓ_{k})", 2));
add(EQ("*p*_{k+1} = TGD.step(*p*_{k}, ∇_{p}ℓ_{k})", 3));
add(P0("The loss ends with VERDICT: PASS or FAIL. The loop starts from the zero-shot instructions *p*_{1} = *p*_{0} and stops when the query executes and the verdict is PASS, or after *K* = 4 iterations. The step LLM returns the new prompt between `<IMPROVED_VARIABLE>` tags. In this *instance-level* mode the prompt is optimised per question; in *prompt-level* mode (option `--carry`) the optimised prompt is carried to the next question."));
add(H2("Step 1: Reading What the Question Requires"));
add(P("A deterministic intent extractor (no LLM) reads the question with phrase lists stored in a configuration file. It records, for example, whether the question asks for the latest test (“most recent”, “still viable”), a threshold and its direction (“below 75%”), stock (“available”, “viable stock”), years or date bounds, a no-retest condition, a storage-limit condition, a count, grouping (“for each”), and the entity being returned (lot or variety). The intent decides which rules and tests apply. Table III shows how often each question-dependent rule is activated on the benchmark."));
add(H2("Step 2: Checking the SQL with Domain Rules"));
add(P("Thirteen rules in four groups check the query text and its result. *Temporal* rules: TEMP-LATEST (a latest-test question must select the latest test per lot), TEMP-PERLOT (a MAX(test_date) subquery must be correlated with the lot, not taken over the whole table), TEMP-RANGE (every stated year bound must appear) and TEMP-NORETEST. *Domain* rules: DOM-THRESHOLD (the stated threshold and direction), DOM-STOCK (quantity above zero), DOM-DOUBLECOUNT (do not subtract distributions from net stock) and DOM-STORAGE (out of range means temperature *or* humidity above the limit). *Join and aggregation* rules: JOIN-KEY, AGG-GROUP, AGG-COUNT and AGG-BARE. A SCHEMA rule covers unknown tables and columns. Every rule has an identifier, a category and a fix written in plain words. Thresholds and phrases live in a JSON file, so another seed bank can change them without code changes."));
add(tcaption("III", "Rule Activation by Intent on the 60 Questions"));
add(TABLE([2600, 1400], [
  ["Rule (activated when the question…)", "Questions"],
  ["AGG-GROUP (…asks “for each”)", "23"],
  ["TEMP-LATEST (…asks for the latest test)", "18"],
  ["DOM-THRESHOLD (…states a germination threshold)", "14"],
  ["AGG-COUNT (…asks “how many”)", "13"],
  ["TEMP-RANGE (…states a year or date bound)", "12"],
  ["DOM-STOCK (…requires stock)", "6"],
  ["DOM-STORAGE (…mentions storage limits)", "5"],
  ["TEMP-NORETEST (…excludes retested lots)", "2"],
]));
add(P0("JOIN-KEY, DOM-DOUBLECOUNT, AGG-BARE and SCHEMA are checked on every query.", { run: { size: PT(8) } }));
add(H2("Step 3: Metamorphic Tests: Change the Data, Check the Answer Moves Correctly"));
add(P("Rules read the SQL; metamorphic tests read its *behaviour*. Each test copies the database into memory, makes one controlled change, re-runs the generated query in read-only mode, and compares the new answer with the answer the question’s intent predicts. No gold answer is needed. Six relations are implemented (Table IV); at most four tests run per query, and changed rates are placed 15 points past the threshold so that rounding cannot hide a failure. Tests are skipped when they would not be meaningful, for example for “top 5” queries whose membership can legitimately shift."));
add(tcaption("IV", "Metamorphic Relations Used by the Validator"));
add(TABLE([1150, 2250, 1640], [
  ["Relation", "Controlled change", "Expected effect"],
  ["MR-LATEST", "add a newer test on the other side of the threshold for a returned lot", "the lot leaves the answer"],
  ["MR-LATEST-ADD", "add a newer failing test for a lot that passed before", "the lot enters the answer"],
  ["MR-STOCK", "set a returned lot’s stock to 0", "the lot leaves the answer"],
  ["MR-NORETEST", "add a later passing retest for a returned lot", "the lot leaves the answer"],
  ["MR-RANGE", "add a test dated outside the asked period", "answer unchanged"],
  ["MR-STORAGE-OR", "add a reading above the temperature limit, humidity within", "the lot’s count rises"],
], { align: [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT] }));
add(H2("Step 4: Grounded Loss, Validator Veto and Typed Gradients"));
add(P("VG-TextGrad changes three parts of the baseline loop (Fig. 1). *Grounded loss:* the evaluator receives the validator’s findings inside `<VALIDATION_FINDINGS>` tags and is told to treat failed metamorphic tests as strong evidence. *Veto:* an iteration passes only if the evaluator says PASS **and** the validator has no findings, so an LLM judge cannot wave a validated error through. *Typed gradient:* the gradient LLM writes one bullet per finding, starting with its rule identifier (for example “[TEMP-LATEST] …”), plus at most two further bullets for problems the evaluator found. In symbols, with validator report *V*_{k}:"));
add(EQ("*V*_{k} = Val(*q*, *ŷ*_{k}, *r*_{k}, *D*),    ℓ_{k} = *L*(*q*, *S*, *ŷ*_{k}, *r*_{k}, *V*_{k})", 4));
add(EQ("pass_{k} = [*r*_{k} executes] ∧ [ℓ_{k} = PASS] ∧ [*V*_{k} = ∅]", 5));
add(IMG("fig1_pipeline.png", 300, 421));
add(caption("Fig. 1.  VG-TextGrad pipeline. Steps 1, 3 and 4 are deterministic and never see the gold answer; steps 2, 5, 6 and 7 are LLM calls. The prompt, not the SQL, is the optimised variable.", false));
add(H2("Rule Memory for Prompt-Level Optimization"));
add(P("When prompts are carried across questions, a long optimised prompt can fill up with advice that does not apply. In prompt-level mode VG-TextGrad keeps a *rule memory*: typed gradient bullets are stored under their rule identifier (at most two per rule), and each new question starts from the base instructions plus only the lessons whose rules its intent activates. Here the gradient is told to write general rules, never specific lot numbers."));
add(H2("Safety: A Read-Only Sandbox"));
add(P("Generated SQL runs on a read-only connection; only a single SELECT or WITH statement is accepted, and a progress handler stops any query after 10 seconds. Metamorphic tests run on in-memory copies that are discarded after use, so the stored database never changes."));

// VI
add(H1("Evaluation Plan: Methods, Metrics and Statistics"));
add(H2("Seven Methods, Including Two Ablations"));
add(P("Table V lists the compared methods. All use the same schema description and base instructions. The ablations isolate the two new ingredients: *Validator-retry* gives the validator’s findings straight to the generator without TextGrad, and *VG-TextGrad (static)* uses the rules without metamorphic tests."));
add(tcaption("V", "Compared Methods"));
add(TABLE([1500, 2640, 900], [
  ["Method", "Feedback used to improve the query", "Max LLM calls"],
  ["Zero-shot", "none", "1"],
  ["Few-shot", "none (4 demonstrations)", "1"],
  ["Error-retry", "raw execution error, query rewritten", "4"],
  ["TextGrad", "LLM loss from execution result, prompt rewritten", "14"],
  ["Validator-retry", "validator findings, query rewritten", "4"],
  ["VG-TextGrad (static)", "rules only, TextGrad loop", "14"],
  ["**VG-TextGrad**", "rules + metamorphic tests, TextGrad loop", "14"],
], { align: [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.CENTER] }));
add(P0("With *K* = 4, a TextGrad method makes four calls per failed iteration (generate, loss, gradient, step) and two in the last, so at most 14.", { run: { size: PT(8) } }));
add(H2("What We Measure"));
add(Item("1)", "**Execution accuracy (EX):** the final result matches the gold result on the benchmark database. Matching is relaxed in the usual way: row order, column order, aliases and extra predicted columns are ignored, each gold column must map to a distinct predicted column, numbers are compared to two decimals and text without case."));
add(Item("2)", "**Temporal robust accuracy (TRA):** EX on the benchmark database *and* on each of five changed states. Each state adds 14 newer germination tests (some crossing 75%), empties six lots and restocks three, adds three distributions and six storage readings, and adds next-year records (dated 2027-02-10) for four lots. States where the gold “top-k” answer has a tie are redrawn. The gold query is the oracle, so TRA is used for evaluation only."));
add(Item("3)", "**Rule compliance:** the share of final queries with no validator finding. For the VG methods this is partly circular, because they are optimised against the validator, so we report it as a diagnostic, not as accuracy."));
add(Item("4)", "**Cost and behaviour:** successful-query rate, first-attempt accuracy, average iterations and LLM calls, and error categories of the first and the final attempt (syntax, unknown column or table, aggregation misuse, wrong result, empty result)."));
add(H2("Model and Settings"));
add(P("The runner supports any OpenAI-compatible endpoint. Our configuration uses the Groq API with the open-weight model gpt-oss-20b [26], temperature 0, low reasoning effort and at most 4,096 output tokens. If the provider has retired a model, the client switches to an available one; the model actually used for every answer, and any switch, is written to the run’s `config.json`."));
add(H2("Statistics"));
add(P("Each method answers every question three times (`--repeats 3`), and we report the mean and standard deviation over the repeats. Accuracies get 95% Wilson intervals [24]. Because all methods answer the same questions, methods are compared pairwise with the exact McNemar test [23] on the questions where exactly one of the two is right, with Holm’s correction [25] across the ten planned comparisons."));

// VII
add(H1("Results"));
add(P("Sections VII-A to VII-D are offline results: they need no LLM, are fully reproducible (`eval_validator.py`, `eval_robustness.py`), and are reported exactly as produced. Section VII-E is the LLM comparison, which has not been run yet."));
add(H2("Does the Validator Raise False Alarms on Correct SQL?"));
add(P("A validator that flags correct queries would push TextGrad away from right answers. We ran it on all 60 gold queries and on 18 correct rewrites in other SQL styles (window functions such as ROW_NUMBER and RANK, common table expressions, NOT EXISTS, ORDER BY … LIMIT 1 subqueries, conditional sums, strftime or BETWEEN for years, USING joins). It produced **no findings** on any of the 78 correct queries."));
add(H2("Does the Validator Catch Realistic Mistakes?"));
add(P("We injected 12 types of semantic mistake into the gold queries (Fig. 2), such as dropping the latest-test condition, taking the newest test of the whole table, using the earliest test, moving a threshold, turning OR into AND, subtracting distributions from net stock, and joining on the wrong key. We kept only mutants that execute and return a *different* answer from gold, that is, mistakes execution feedback would accept: 105 mutants. Static rules flagged 104 (99%); with metamorphic tests all 105 (100%) were flagged. The one mutant missed by the rules had a reversed threshold direction; a metamorphic test caught it. Metamorphic tests also failed, independently of the rules, for about half of the latest-test mistakes and for every stock, date-bound and no-retest mistake. For structural mistakes such as a missing GROUP BY no relation applies, and the rules do the work (Fig. 2)."));
add(P("These figures are optimistic. The rules were refined on this benchmark until the false alarms disappeared, so they describe a development set. An independent question set written by someone who did not write the rules is needed before they can be read as generalisation."));
add(IMG("fig2_mutants.png", 330, 252));
add(caption("Fig. 2.  Injected mistakes by type (number of mutants in brackets). Blue: share flagged by static rules. Orange: share for which a metamorphic test also failed. With both, 105 of 105 were flagged.", false));
add(H2("Can a Wrong Query Look Right on One Database State?"));
add(P("Nine of the injected mutants returned *exactly* the gold answer on the benchmark database, so ordinary execution accuracy scores them as correct. On the five changed states, five of them diverged from gold (Table VI): four had dropped a date bound and one had dropped the no-retest condition. Today these happen to give the right rows; when next year’s records arrive, they will not. The validator flagged four of the five without any gold answer. The other four mutants gave the gold answer on every state, so we have no evidence that they are wrong. TRA accepted all 60 gold queries and all 18 correct rewrites, so it did not penalise any correct query."));
add(tcaption("VI", "Mutants That Match Gold on the Benchmark Database"));
add(TABLE([3240, 1800], [
  ["Outcome on five changed states", "Mutants"],
  ["Diverge from gold (hidden mistakes)", "5"],
  ["   of which: dropped date bound", "4"],
  ["   of which: dropped no-retest condition", "1"],
  ["   of which: flagged by the validator", "4"],
  ["Same as gold on every state", "4"],
  ["Correct queries rejected by TRA", "0 of 78"],
]));
add(H2("How Much Does Validation Cost?"));
add(P("On the 60 gold queries the validator ran 28 metamorphic tests in total, on 14 questions; the other questions have no applicable relation and are checked by rules alone. Validation took about 6 ms per query on a laptop, which is negligible next to one LLM call. The validator adds no LLM calls."));
add(H2("LLM Comparison of the Seven Methods (Pending)"));
add(P("Table VII shows the layout of the main result. We have not yet completed a run with a real LLM: an earlier attempt was blocked by the provider (HTTP 403) and is not a result, and the pipeline was otherwise tested only with an offline mock model whose numbers we do not report. The table will be filled from `results/<run>/stats.md` after `run_experiments.py --repeats 3`."));
add(tcaption("VII", "Main Result (to Be Filled After the LLM Runs)"));
add(TABLE([1560, 870, 870, 870, 870], [
  ["Method", "EX (%)", "TRA (%)", "Rule comp. (%)", "Avg. calls"],
  ["Zero-shot", "—", "—", "—", "—"],
  ["Few-shot", "—", "—", "—", "—"],
  ["Error-retry", "—", "—", "—", "—"],
  ["TextGrad", "—", "—", "—", "—"],
  ["Validator-retry", "—", "—", "—", "—"],
  ["VG-TextGrad (static)", "—", "—", "—", "—"],
  ["VG-TextGrad", "—", "—", "—", "—"],
]));
add(P("Three comparisons answer the research questions: VG-TextGrad against TextGrad (does grounded evidence help the optimizer?), against Validator-retry (does the TextGrad loop add value beyond feeding findings back?), and against VG-TextGrad (static) (do metamorphic tests add value beyond rules?). Results will also be broken down by category and tier, since we expect the largest differences on Tier-3 temporal and domain questions."));

// VIII
add(H1("Worked Example: The “Latest Germination Test” Mistake"));
add(P("Question T3-01 asks for lots whose most recent germination rate is below 75%. The gold query returns 38 lots:"));
add(CODE(["SELECT g.lot_id, g.germination_rate", "FROM GerminationTest g", "WHERE g.test_date = (SELECT MAX(g2.test_date)", "        FROM GerminationTest g2", "        WHERE g2.lot_id = g.lot_id)", "  AND g.germination_rate < 75;"]));
add(P0("A common wrong query, here produced by the drop-latest mutation, forgets the latest-test condition:"));
add(CODE(["SELECT g.lot_id, g.germination_rate", "FROM GerminationTest g", "WHERE g.germination_rate < 75;"]));
add(P("It runs without error and returns 64 rows covering 40 lots: every failed test of every lot, so lots repeat, and two lots appear whose newer tests passed. Execution feedback sees nothing wrong. The validator reports, without the gold answer:"));
add(Item("–", "*Static (TEMP-LATEST):* “The question refers to the most recent germination result, but the SQL never selects the latest test per lot.”"));
add(Item("–", "*Metamorphic (MR-LATEST):* “after adding a newer germination test of 90% for every lot of lot ‘1’, the query still returned ‘1’. The answer should depend only on the latest test.”"));
add(P("In VG-TextGrad these findings block a PASS and become a gradient bullet beginning “[TEMP-LATEST]”, which the step LLM folds into the prompt. A second mutation, taking the newest test of the *whole table* instead of each lot, returns a single row and is caught by TEMP-PERLOT. These messages are actual validator output on injected mistakes; they are not traces of an LLM run."));

// IX
add(H1("Limitations and Threats to Validity"));
add(Item("1)", "**Simulated monitoring data.** Only the accessions are real; lots, tests, readings and distributions are simulated, and the thresholds are assumptions. Results show behaviour on realistic structure, not on real genebank operations."));
add(Item("2)", "**Development-set validator figures.** The rules were tuned on the same 60 questions; a held-out question set is needed."));
add(Item("3)", "**Small benchmark, one domain.** Sixty questions over one schema limit statistical power and generality; the paired tests and confidence intervals make this visible rather than remove it."));
add(Item("4)", "**Relaxed matching can over-credit.** Ignoring extra columns can accept an answer with a surplus column. TRA reduces but does not remove such cases."));
add(Item("5)", "**Rule coverage.** The validator only knows the error types it has rules and relations for; an unseen kind of mistake passes silently, and rule compliance is partly circular for the VG methods."));
add(Item("6)", "**Model and provider.** Results will depend on the chosen model; the runner logs the model used and supports other providers for replication."));

// X
add(H1("Ethics, Data Use and Reproducibility"));
add(P("The system is decision support only and makes no agricultural decision. Model-written SQL runs in a read-only sandbox. Accession data come from Genesys and are used under its terms of use [18]; no personal data are involved, and farmer-group names in the simulated distributions are invented. The code, database builder, benchmark, rules, prompts and evaluation scripts are in the project repository (github.com/hemakowshik/seedbank-textgrad-sql). Every run stores each prompt, query, loss and gradient, so any reported number can be traced to its trace."));

// XI
add(H1("Conclusion and Future Work"));
add(P("Seed-bank questions are easy to answer *almost* right. We combined TextGrad with a validator that needs no answer key: it reads the question’s intent, checks the SQL with domain and temporal rules, and tests its behaviour on controlled database changes. Offline, the validator raised no false alarms on 78 correct queries and flagged all 105 injected wrong-but-running mistakes on the development set, and five injected mistakes that matched the gold answer on the benchmark database were exposed by changed states. Next we will run the seven-method LLM comparison with repeated runs, write an independent held-out question set, measure how the rule memory transfers across questions, try several model sizes, and test the approach with practitioners and openly licensed monitoring records."));

// References
add(new Paragraph({ children: [new TextRun({ text: "References", font: FONT, size: PT(10), smallCaps: true })], alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 }, keepNext: true }));
const REFS = [
  "Z. Hong, Z. Yuan, Q. Zhang, H. Chen, J. Dong, F. Huang, and X. Huang, “Next-generation database interfaces: A survey of LLM-based text-to-SQL,” arXiv:2406.08426, 2024.",
  "T. Yu *et al.*, “Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task,” in *Proc. EMNLP*, 2018, pp. 3911–3921.",
  "J. Li *et al.*, “Can LLM already serve as a database interface? A BIg bench for large-scale database grounded text-to-SQLs,” in *Proc. NeurIPS*, 2023.",
  "L. Nan, Y. Zhao, W. Zou, N. Ri, J. Tae, E. Zhang, A. Cohan, and D. Radev, “Enhancing text-to-SQL capabilities of large language models: A study on prompt design strategies,” in *Findings of EMNLP*, 2023, pp. 14935–14956.",
  "B. Wang *et al.*, “MAC-SQL: A multi-agent collaborative framework for text-to-SQL,” in *Proc. COLING*, 2025, pp. 540–557.",
  "W. Mao, R. Wang, J. Guo, J. Zeng, C. Gao, P. Han, and C. Liu, “Enhancing text-to-SQL parsing through question rewriting and execution-guided refinement,” in *Findings of ACL*, 2024, pp. 2009–2024.",
  "S. Piao, J. Lee, and S. Park, “LitE-SQL: A lightweight and efficient text-to-SQL framework with vector-based schema linking and execution-guided self-correction,” arXiv:2510.09014, 2025.",
  "A. Jain and M. Shrivastava, “Reflect-SQL: A self-reflection based framework for text-to-SQL,” arXiv:2609.02944, 2026.",
  "H. Zheng, Y. Gou, and W. Zhang, “ZAS-SQL: Distilling rules from failures for zero-shot text-to-SQL,” arXiv:2606.08245, 2026.",
  "R. Pryzant, D. Iter, J. Li, Y. T. Lee, C. Zhu, and M. Zeng, “Automatic prompt optimization with “gradient descent” and beam search,” in *Proc. EMNLP*, 2023, pp. 7957–7968.",
  "M. Yuksekgonul *et al.*, “Optimizing generative AI by backpropagating language model feedback,” *Nature*, vol. 639, no. 8055, pp. 609–616, 2025, doi: 10.1038/s41586-025-08661-4.",
  "S. Gurajada, E. Kandogan, and S. Rahman, “Effectiveness of prompt optimization in NL2SQL systems,” arXiv:2505.20591, 2025, doi: 10.1145/3735079.3735325.",
  "T. Y. Chen, S. C. Cheung, and S. M. Yiu, “Metamorphic testing: A new approach for generating next test cases,” Hong Kong Univ. Sci. Technol., Tech. Rep. HKUST-CS98-01, 1998.",
  "S. Segura, G. Fraser, A. B. Sanchez, and A. Ruiz-Cortés, “A survey on metamorphic testing,” *IEEE Trans. Softw. Eng.*, vol. 42, no. 9, pp. 805–824, 2016.",
  "M. Rigger and Z. Su, “Testing database engines via query partitioning,” *Proc. ACM Program. Lang.*, vol. 4, no. OOPSLA, 2020.",
  "R. Zhong, T. Yu, and D. Klein, “Semantic evaluation for text-to-SQL with distilled test suites,” in *Proc. EMNLP*, 2020, pp. 396–411.",
  "Y. Jia and M. Harman, “An analysis and survey of the development of mutation testing,” *IEEE Trans. Softw. Eng.*, vol. 37, no. 5, pp. 649–678, 2011.",
  "Global Crop Diversity Trust, “Genesys: Plant genetic resources portal,” accession list of ICRISAT (IND002) and terms of use, https://www.genesys-pgr.org, accessed Nov. 2026.",
  "USDA-ARS, “GRIN-Global: Germplasm Resource Information Network,” https://www.grin-global.org.",
  "F. R. Hay *et al.*, “CGIAR genebank viability data reveal inconsistencies in seed collection management,” *Global Food Security*, vol. 30, art. 100557, 2021.",
  "FAO, *Genebank Standards for Plant Genetic Resources for Food and Agriculture*. Rome, Italy: FAO, 2014.",
  "Z. Zhang, J. Zhang, H. Liu, Q. Lv, J. Yang, K. Cai, and K. Wang, “AgriWorld: A world tools protocol framework for verifiable agricultural reasoning with code-executing LLM agents,” arXiv:2602.15325, 2026.",
  "Q. McNemar, “Note on the sampling error of the difference between correlated proportions or percentages,” *Psychometrika*, vol. 12, no. 2, pp. 153–157, 1947.",
  "E. B. Wilson, “Probable inference, the law of succession, and statistical inference,” *J. Amer. Statist. Assoc.*, vol. 22, no. 158, pp. 209–212, 1927.",
  "S. Holm, “A simple sequentially rejective multiple test procedure,” *Scand. J. Statist.*, vol. 6, no. 2, pp. 65–70, 1979.",
  "OpenAI, “gpt-oss-120b & gpt-oss-20b model card,” arXiv:2508.10925, 2025.",
];
REFS.forEach((r, i) => add(new Paragraph({
  children: [new TextRun({ text: `[${i + 1}]\t`, font: FONT, size: PT(8) }), ...runs(r, { size: PT(8) })],
  indent: { left: 360, hanging: 360 }, tabStops: [{ type: TabStopType.LEFT, position: 360 }],
  alignment: AlignmentType.JUSTIFIED, spacing: { before: 0, after: 20 } })));

const page = { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1440, left: 900, right: 900 } };
const doc = new Document({
  creator: "SeedSQL team", title: "Validation-Guided TextGrad for Seed-Bank Text-to-SQL",
  styles: { default: { document: { run: { font: FONT, size: PT(10) } } } },
  sections: [
    { properties: { page }, children: title },
    { properties: { page, type: SectionType.CONTINUOUS, column: { count: 2, space: 360, equalWidth: true } }, children: B },
  ],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(process.argv[2] || "paper.docx", b); console.log("ok"); });
