// Builds SeedSQL paper v2 in the layout of the team's earlier draft (single column, Calibri).
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType, WidthType,
  BorderStyle, ShadingType, TabStopType, VerticalAlign, Footer, PageNumber, LevelFormat, HeadingLevel,
} = require("docx");

const FONT = "Calibri", INK = "1F1E1D", GREY = "5E5D59";
const W = 10078;                       // text width (Letter, draft margins)

function runs(text, base = {}) {      // *italic*, _{sub}, ^{sup}, `code`
  const out = [], re = /(\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\}|`[^`]+`)/g;
  let last = 0, m;
  const push = (t, x = {}) => { if (t) out.push(new TextRun({ text: t, font: FONT, color: INK, ...base, ...x })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const t = m[0];
    if (t[0] === "*") push(t.slice(1, -1), { italics: true });
    else if (t[0] === "_") push(t.slice(2, -1), { subScript: true });
    else if (t[0] === "^") push(t.slice(2, -1), { superScript: true });
    else push(t.slice(1, -1), { font: "Courier New", size: 20 });
    last = m.index + t.length;
  }
  push(text.slice(last));
  return out;
}
const P = (t, o = {}) => new Paragraph({ children: o.children || runs(t, o.run), spacing: { after: o.after ?? 150, line: 295 },
  alignment: o.align, keepNext: o.keepNext });
const lead = (label, t) => new Paragraph({ children: [new TextRun({ text: label + " ", font: FONT, bold: true, color: INK }), ...runs(t)],
  spacing: { after: 150, line: 295 } });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT, color: INK })],
  spacing: { before: 360, after: 120 } });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT, color: INK })],
  spacing: { before: 200, after: 120 } });
const NUM = (t, ref = "num", level = 0) => new Paragraph({ numbering: { reference: ref, level }, children: runs(t),
  spacing: { after: 80, line: 295 } });
const BUL = (t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, children: runs(t), spacing: { after: 80, line: 295 } });

const shade = { type: ShadingType.CLEAR, color: "auto", fill: "F3F3F3" };
const CODE = (lines) => lines.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l || " ", font: "Courier New", size: 19, color: INK })],
  shading: shade, indent: { left: 140, right: 140 }, keepNext: i < lines.length - 1,
  spacing: { before: i === 0 ? 120 : 0, after: i === lines.length - 1 ? 200 : 0, line: 250 } }));
const EQ = (t, n) => new Paragraph({
  children: [new TextRun({ text: "\t" }), ...runs(t, { font: "Cambria Math" }), new TextRun({ text: `\t(${n})`, font: FONT, color: INK })],
  tabStops: [{ type: TabStopType.CENTER, position: W / 2 }, { type: TabStopType.RIGHT, position: W }],
  spacing: { before: 100, after: 160 } });

const border = { style: BorderStyle.SINGLE, size: 6, color: "E8E5DC" };
const borders = { top: border, bottom: border, left: border, right: border };
function TABLE(widths, rows, opt = {}) {
  const scale = W / widths.reduce((a, b) => a + b, 0);
  const ws = widths.map((w) => Math.round(w * scale));
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: ws,
    rows: rows.map((r, ri) => new TableRow({ tableHeader: ri === 0, cantSplit: true,
      children: r.map((c, ci) => new TableCell({
        width: { size: ws[ci], type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
        shading: ri === 0 ? shade : undefined, margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: runs(String(c), { size: 21, color: ri === 0 ? "555450" : INK }),
          alignment: opt.center && opt.center.includes(ci) ? AlignmentType.CENTER : AlignmentType.LEFT,
          keepNext: ri === 0, spacing: { after: 0, line: 260 } })] })) })) });
}
const TCAP = (label, t) => new Paragraph({ children: [new TextRun({ text: label + " ", font: FONT, bold: true, color: INK }), ...runs(t)],
  spacing: { before: 120, after: 120 }, keepNext: true });
const AFTER = () => new Paragraph({ children: [], spacing: { after: 120 } });
const IMG = (f, w, h) => new Paragraph({ children: [new ImageRun({ type: "png", data: fs.readFileSync(f),
  transformation: { width: w, height: h }, altText: { title: f, description: f, name: f } })], spacing: { before: 120, after: 80 },
  keepNext: true, alignment: AlignmentType.CENTER });
const FCAP = (t) => new Paragraph({ children: [new TextRun({ text: t, font: FONT, size: 19, color: GREY })], spacing: { after: 220 } });

// ============================================================================================ content
const C = [];
const add = (...x) => x.flat().forEach((e) => C.push(e));

add(new Paragraph({ children: [new TextRun({ text: "TextGrad-Guided Text-to-SQL for Community Seed-Bank Viability and Climate-Resilience Analytics", font: FONT, size: 48, color: INK })], spacing: { after: 160, line: 300, lineRule: "auto" } }));
add(new Paragraph({ children: [new TextRun({ text: "Draft for review, not for submission. ", font: FONT, bold: true, color: INK }),
  new TextRun({ text: "The LLM comparison (Section VII-E) is left blank until the benchmark runs are complete. All other numbers come from the current code and database.", font: FONT, color: INK })], spacing: { after: 150 } }));
add(new Paragraph({ children: [new TextRun({ text: "GAYATHRI PRIYA V, GONU GUNTLA HEMA KOWSHIK, BHAVIN G KAMAT", font: FONT, bold: true, color: INK })], spacing: { after: 44 } }));
add(new Paragraph({ children: [new TextRun({ text: "Department of Computer Science and Engineering (AI & ML), PES University, Bengaluru, India", font: FONT, color: INK })], spacing: { after: 44 } }));
add(new Paragraph({ children: [new TextRun({ text: "Guide: [Guide name]", font: FONT, color: INK })], spacing: { after: 500 } }));

add(H1("Abstract"));
add(P("Community seed banks keep records of seed lots, germination tests, storage conditions and distributions, but the staff who need answers from these records rarely write SQL. Large language models (LLMs) can translate questions into SQL, yet their queries often run without error and still return the wrong rows, for example by using every germination test when only a lot's most recent test matters. Execution feedback cannot see such errors, and in deployment there is no reference answer to compare with. We study TextGrad-guided prompt refinement for this domain and add a validator that needs no reference answer. The validator reads what the question asks for, checks the SQL against 13 configurable domain and temporal rules, and runs metamorphic tests: it makes a controlled change to an in-memory copy of the database, such as adding a newer passing test for a returned lot, and checks that the answer changes the way the question requires. Its findings are given to the TextGrad evaluator, block a PASS, and become gradients tagged with the rule that failed. We contribute a database built from 66 real ICRISAT accessions downloaded from Genesys with simulated monitoring records, a benchmark of 60 questions with hand-written gold SQL, temporal robust accuracy (a check of each answer on five changed database states), and a comparison of seven methods. Offline, the validator raised no false alarm on 78 correct queries and flagged all 105 injected wrong-but-running queries, although the rules were developed on the same questions. Five injected queries returned exactly the gold answer on the benchmark database but went wrong on changed states. [Main LLM finding to be added after the experiments.]"));
add(new Paragraph({ children: [new TextRun({ text: "Index Terms: ", font: FONT, bold: true, color: INK }), ...runs("Text-to-SQL, large language models, TextGrad, prompt optimization, metamorphic testing, execution feedback, seed banks, genebanks.")], spacing: { after: 400 } }));

// I
add(H1("I. Introduction"));
add(P("Community seed banks conserve locally adapted crop varieties such as finger millet, foxtail millet, sorghum and pulses. They track each seed lot from regeneration through storage, periodic germination testing and distribution to farmers. Coordinators regularly ask questions that combine these records: which lots have fallen below a viability threshold and need retesting, which drought-tolerant varieties still have viable stock, and which lots have spent the longest time outside recommended storage conditions. Answering them requires joins, aggregation and per-lot temporal logic, which most staff cannot write in SQL."));
add(P("LLM-based Text-to-SQL systems can translate such questions into SQL [2], [5]. Their errors fall into two groups. Execution errors (unknown columns, syntax errors) are visible because the database rejects the query. Semantic errors are harder: the query runs and returns rows, but applies the wrong filter, joins incorrectly, or uses every germination test instead of the most recent one. Execution-guided self-correction mainly addresses the first group [3], [9], [10]."));
add(P("TextGrad [1] treats a pipeline of LLM calls like a computation graph. An LLM evaluator produces a natural-language loss, an LLM converts it into a textual gradient aimed at a chosen variable, and an optimizer LLM rewrites that variable. Applied to Text-to-SQL, the variable can be the generator's system prompt. The weak point is the loss: if the evaluator cannot see that a query ignores the latest-test logic, the gradient cannot fix it either, and a reference answer is not available in deployment."));
add(P("Our first version used execution feedback and an LLM evaluator only. In this version we give the evaluator evidence that does not depend on the reference answer. A deterministic validator extracts the question's intent, checks the SQL with seed-bank rules, and tests how the query behaves when the data changes. For example, if lot 12 is returned for \"lots whose most recent germination rate is below 75%\", adding a newer test of 90% for lot 12 must remove it from the answer. If it does not, the query is not using the latest test."));
add(lead("Research question.", "Does grounding TextGrad's loss and gradient in a reference-free domain and temporal validator improve Text-to-SQL accuracy and robustness for community seed-bank analytics, compared with plain TextGrad, error-retry, few-shot and zero-shot prompting?"));
add(new Paragraph({ children: [new TextRun({ text: "Contributions.", font: FONT, bold: true, color: INK })], spacing: { after: 120 } }));
add(NUM("A seed-bank relational database built from 66 real ICRISAT genebank accessions published on Genesys [16], with simulated lots, germination tests, storage readings and distributions."));
add(NUM("A benchmark of 60 natural-language questions in five categories and three complexity tiers, each with hand-written gold SQL whose result is checked to be non-empty and well-defined."));
add(NUM("A validator that needs no reference answer: intent extraction, 13 configurable rules and six intent-conditioned metamorphic tests on in-memory copies of the database."));
add(NUM("Validation-guided TextGrad (VG-TextGrad): the validator's findings ground the loss, veto a PASS, and become typed gradients tagged by rule, with a rule memory for prompt-level optimization."));
add(NUM("Temporal robust accuracy, which re-checks each answer on five changed database states, and an offline evaluation of the validator by injecting realistic mistakes into the gold queries."));
add(NUM("An open implementation: a read-only execution sandbox, an experiment runner for seven methods with paired statistics, and a browser interface that shows each refinement step."));
add(P("We do not claim that TextGrad, execution-guided refinement or metamorphic testing is new. The contribution is using reference-free semantic checks as the signal for TextGrad, in a domain whose questions depend on temporal, per-lot logic, with ablations that separate the value of the validator from the value of the TextGrad loop. Section II reviews related work, Sections III–VI describe the formulation, method, data and protocol, Section VII reports results, and Sections VIII–X discuss the findings, limitations and future work."));

// II
add(H1("II. Related Work"));
add(lead("LLM-based Text-to-SQL.", "A recent survey [5] describes LLM-based Text-to-SQL as a natural-language interface to databases in which the model receives the question and the schema and generates executable SQL. Benchmarks such as Spider [6] and BIRD [7] established execution-based evaluation, where a prediction is judged by its result rather than its text. Zhong et al. [8] showed that a single database can make a wrong query look right and proposed evaluating on a suite of databases; our temporal robust accuracy follows the same idea with seed-bank specific changes. Nan et al. [2] showed that prompt design choices, such as how the schema is represented and how demonstrations are selected, change accuracy substantially. SQLPrompt [4] improves few-shot prompting with execution-based consistency decoding, choosing the SQL whose execution result agrees most with the other proposals. This motivates our zero-shot and few-shot baselines."));
add(lead("Execution-guided refinement.", "MAC-SQL [9] refines queries iteratively using execution feedback within a multi-agent framework. DART-SQL [3] combines question rewriting with execution-guided refinement. LitE-SQL [10] categorises execution errors as syntax errors, unknown columns, unknown tables and others, and compares their frequency before and after self-correction. We adopt a similar error taxonomy and extend it with result-level categories, because a query that executes can still be wrong."));
add(lead("LLM-as-judge refinement.", "Reflect-SQL [11] uses an LLM-as-a-judge scoring mechanism within feedback loops to refine results at several stages. Our evaluator plays a similar judging role, but its verdict is checked against the validator and it drives prompt optimization rather than candidate selection."));
add(lead("Textual-gradient prompt optimization.", "ProTeGi [12] optimises prompts with natural-language \"gradients\" and beam search. TextGrad [1] generalises the idea into an automatic-differentiation-style framework covering both instance optimization and prompt optimization across coding, science and medical tasks. Prompt optimization has also been studied for production NL2SQL systems [13]. To our knowledge, TextGrad has not been evaluated for Text-to-SQL in agricultural or genebank settings."));
add(lead("Testing without a known answer.", "Metamorphic testing [14] checks a program when the correct output is unknown, by checking a relation between its outputs on related inputs. Mutation testing [15] measures a checker by injecting realistic faults and counting how many it detects. We use metamorphic relations to check generated queries, and mutation testing to measure our validator."));
add(lead("Genebank and seed-bank information systems.", "Genebanks document accessions with standardised passport descriptors and publish them through portals such as Genesys [16]. Management systems such as GRIN-Global [17] record inventory and viability testing. Studies of CGIAR genebanks [18] show that viability monitoring data are central to conservation decisions, and the FAO Genebank Standards [19] set expectations for storage and monitoring. We found no prior work applying textual-gradient prompt optimization to natural-language querying of seed-bank records."));

// III
add(H1("III. Problem Formulation"));
add(P("Let *D* be a relational database with schema *S*, and *q* a natural-language question. A generator *G*, an LLM, is conditioned on a system prompt *p* (the instructions), the schema description and the question, and returns a SQL query. An executor *E* runs the query on *D* in read-only mode and returns either a result set *R* or an error message *e*:", { keepNext: true }));
add(EQ("ŷ = G(p, S, q),      r = E(ŷ, D) ∈ {rows R, error e}", 1));
add(P("For evaluation only, each question has a gold query *y*^{*} with result *R*^{*} = *E*(*y*^{*}, *D*). A prediction is correct when match(*R*, *R*^{*}) holds (Section VI-A). In deployment *R*^{*} is unknown, so refinement cannot depend on it."));
add(P("TextGrad treats *p* as a trainable variable. An evaluator LLM *L* produces a textual loss from observable information, and a gradient LLM Γ produces feedback directed at *p*. In VG-TextGrad both also receive the validator report *V*_{k}, which is computed from the question, the query and the database only:", { keepNext: true }));
add(EQ("V_{k} = Val(q, ŷ_{k}, r_{k}, D),     ℓ_{k} = L(q, S, ŷ_{k}, r_{k}, V_{k}),     ∇_{p}ℓ_{k} = Γ(p_{k}, q, ŷ_{k}, r_{k}, ℓ_{k}, V_{k})", 2));
add(P("The Textual Gradient Descent (TGD) step is an LLM call that rewrites the variable:", { keepNext: true }));
add(EQ("p_{k+1} = TGD(p_{k}, ∇_{p}ℓ_{k})", 3));
add(P("The loop starts from the zero-shot prompt, *p*_{1} = *p*_{0}. It stops at the first iteration *k* where the query executes, the loss ends in VERDICT: PASS and the validator has no findings, or at *k* = *K* (the iteration limit). Plain TextGrad is the same loop without *V*_{k} and without the third condition. The objective is to maximise execution accuracy and robustness over the benchmark while keeping the number of LLM calls per question low."));

// IV
add(H1("IV. Methodology"));
add(P("The system follows seven stages: question, intent extraction, SQL generation, read-only execution, validation, evaluation, and TextGrad refinement or stop. Fig. 1 shows how they connect."));
add(IMG("fig1_architecture.png", 640, 293));
add(FCAP("Fig. 1 · system architecture and refinement loop"));
add(P("The top row is one forward pass. The bottom row runs only when the evaluator or the validator rejects a query, and changes the prompt rather than the SQL. Intent extraction, execution and validation are plain code; they never call an LLM and never see the gold query."));
add(H2("A. Validation-guided TextGrad loop"));
add(CODE([
  "Algorithm 1: VG-TextGrad",
  "Input: question q, schema S, database D, initial prompt p0, limit K",
  "p <- p0;  intent <- extract_intent(q)",
  "for k = 1 .. K:",
  "    y_k <- extract_sql( G(p, S, q) )                 # forward pass",
  "    r_k <- E(y_k, D)                                 # read-only execution",
  "    V_k <- validate(q, intent, y_k, r_k, D)          # rules + metamorphic tests",
  "    l_k <- L(q, S, y_k, feedback(r_k), V_k)          # loss + VERDICT",
  "    if r_k is rows and l_k ends with PASS and V_k is empty: return y_k",
  "    if k = K: return y_k",
  "    g_k <- Gamma(p, q, y_k, feedback(r_k), l_k, V_k)  # typed gradient",
  "    p   <- TGD(p, g_k)                               # rewrite the prompt",
]));
add(P("feedback(*r*) is the SQLite error message, or the column names, row count and first rows. Each refinement costs four LLM calls (generate, loss, gradient, step), so with *K* = 4 a question costs at most 14 calls; a question solved on the first attempt costs two. The validator adds no LLM calls. The three changes from plain TextGrad are: the loss is grounded in the validator's findings, the validator can veto a PASS, and the gradient is typed, with one bullet per finding that starts with the rule ID."));
add(H2("B. Intent extraction and domain rules"));
add(P("The intent extractor reads the question with phrase lists stored in a JSON file (domain_rules.json). It records whether the question asks for the latest test (\"most recent\", \"still viable\"), a germination threshold and its direction (\"below 75%\", \"at least 85%\"), stock (\"available\", \"viable stock\"), years or date bounds, a no-retest condition, a storage-limit condition, a count, grouping (\"for each\"), and whether the answer is a list of lots or of varieties. The intent decides which rules and tests apply. Table I lists the rules."));
add(TCAP("Table I.", "Domain and temporal rules used by the validator"));
add(TABLE([1900, 1100, 5000], [
  ["Rule ID", "Category", "What it checks"],
  ["TEMP-LATEST", "temporal", "A \"most recent\" question selects the latest test for each lot before applying a threshold"],
  ["TEMP-PERLOT", "temporal", "A MAX(test_date) subquery is correlated with the lot, not taken over the whole table"],
  ["TEMP-RANGE", "temporal", "Every year or date bound in the question appears in the date filter"],
  ["TEMP-NORETEST", "temporal", "\"No later retest\" questions exclude lots with a later test"],
  ["DOM-THRESHOLD", "domain", "The stated threshold and direction are used (below 75% is rate < 75)"],
  ["DOM-STOCK", "domain", "Stock questions require quantity > 0"],
  ["DOM-DOUBLECOUNT", "domain", "Distributions are not subtracted again from the current stock"],
  ["DOM-STORAGE", "domain", "Out of range means temperature above the limit OR humidity above the limit"],
  ["JOIN-KEY", "join", "Lots join varieties on variety_id; tests, readings and distributions join lots on lot_id"],
  ["AGG-GROUP", "aggregation", "\"For each X\" questions group by X"],
  ["AGG-COUNT", "aggregation", "\"How many\" questions return a count"],
  ["AGG-BARE", "aggregation", "Plain columns next to aggregates are grouped"],
  ["SCHEMA", "schema", "Only tables and columns from the schema are used"],
]));
add(AFTER());
add(P("Thresholds (75% germination, 15 °C, 50% humidity) and phrases live in the JSON file, so another seed bank can change them without code changes. Each finding carries the rule ID, a short piece of evidence and a fix in plain words."));
add(H2("C. Metamorphic tests"));
add(P("Rules read the SQL text; metamorphic tests check its behaviour. Each test copies the database into memory, makes one controlled change, re-runs the query read-only, and compares the new answer with what the question's intent predicts. Table II lists the six relations. At most four tests run per query, and changed germination rates are placed 15 points past the threshold so that small differences cannot hide a failure. Tests are skipped for top-k queries, whose membership can legitimately change."));
add(TCAP("Table II.", "Metamorphic relations"));
add(TABLE([1900, 4300, 2600], [
  ["Relation", "Controlled change to the copy", "Expected effect on the answer"],
  ["MR-LATEST", "Add a newer test on the other side of the threshold for a returned lot", "The lot leaves the answer"],
  ["MR-LATEST-ADD", "Add a newer failing test for a lot that passed before", "The lot enters the answer"],
  ["MR-STOCK", "Set a returned lot's quantity to 0", "The lot leaves the answer"],
  ["MR-NORETEST", "Add a later passing retest for a returned lot", "The lot leaves the answer"],
  ["MR-RANGE", "Add a test dated outside the period in the question", "The answer does not change"],
  ["MR-STORAGE-OR", "Add a reading above the temperature limit with humidity in range", "The lot's out-of-range count rises"],
]));
add(AFTER());
add(H2("D. Prompts"));
add(P("The generator prompt contains the instructions *p*, a schema description that lists allowed values for categorical columns (crop types, drought-tolerance levels, storage locations) and the stated assumptions, and the question. The evaluator is told it has no reference answer and checks executability, tables and join keys, every stated condition and threshold, aggregation and grouping, per-lot \"most recent\" logic, the requested output columns, and plausibility. In VG-TextGrad it also receives the validator's findings between <VALIDATION_FINDINGS> tags and is told to treat a failed metamorphic test as strong evidence of an error. The gradient and step prompts follow the structure of TextGrad's TGD optimizer: the variable, its role, the feedback, and an improved variable returned between <IMPROVED_VARIABLE> tags."));
add(H2("E. Instance-level and prompt-level optimization"));
add(P("In instance-level mode the prompt is reset to *p*_{0} for every question, so refinement adapts to the question at hand. In prompt-level mode (--carry) the optimised prompt is carried to the next question, and the gradient is asked for general rules without lot numbers or names. Because one long prompt collects advice that does not apply to every question, VG-TextGrad keeps a rule memory in this mode: gradient bullets are stored under their rule ID (at most two per rule), and each new question starts from the base instructions plus only the lessons whose rules its intent activates."));
add(H2("F. Baselines and ablations"));
add(TCAP("Table III.", "Compared methods"));
add(TABLE([2300, 5200, 1700], [
  ["Method", "Description", "LLM calls per question"],
  ["Zero-shot", "Instructions, schema and question; one generation", "1"],
  ["Few-shot", "Zero-shot plus four question–SQL demonstrations, none in the test set", "1"],
  ["Error-retry (ablation)", "Re-generate with the raw SQLite error appended until the query executes; no evaluator, no gradient", "1 to K"],
  ["TextGrad", "Algorithm 1 without the validator (LLM loss from execution feedback only)", "2 + 4 per refinement"],
  ["Validator-retry (ablation)", "Validator findings appended to the generator prompt; no evaluator, no TextGrad", "1 to K"],
  ["VG-TextGrad (static) (ablation)", "Algorithm 1 with rules only, no metamorphic tests", "2 + 4 per refinement"],
  ["VG-TextGrad", "Algorithm 1", "2 + 4 per refinement"],
], { center: [2] }));
add(AFTER());
add(P("TextGrad's first iteration is identical to zero-shot, so any difference comes from refinement. Error-retry stops once a query executes, so it cannot repair semantic errors. Validator-retry shows what the validator gives without the TextGrad loop, and VG-TextGrad (static) shows what the metamorphic tests add over the rules."));
add(H2("G. Implementation"));
add(P("The pipeline is written in Python with only the standard library for its core (sqlite3, urllib). The database is opened read-only with PRAGMA query_only. Only single SELECT or WITH statements are accepted, and each query is limited to 10 seconds. Metamorphic tests run on in-memory copies made with the SQLite backup API and are discarded afterwards. The LLM client supports any OpenAI-compatible endpoint; in this study we use openai/gpt-oss-20b [21] served by Groq at temperature 0 with low reasoning effort. If a provider retires a model, the client switches to an available one, and the model actually used for every answer is written to the run's config.json. A browser interface runs SQLite client-side through sql.js and shows every iteration's SQL, result, validator findings, loss, gradient and prompt diff."));

// V
add(H1("V. Dataset and Benchmark"));
add(H2("A. Data source: ICRISAT accessions from Genesys"));
add(P("We downloaded the accession list of ICRISAT (FAO WIEWS code IND002) from Genesys [16]. It contains 149,034 accession records, of which 148,933 have a Genesys DOI. ICRISAT accession numbers start with a crop prefix, which we use to assign the crop: IS and ISS sorghum, IP and ISP pearl millet, ICC chickpea, ICG and GGP groundnut, ICP and ISC pigeon pea, IE finger millet, ISe foxtail millet, IPm proso millet, IEc barnyard millet, IPs kodo millet and IPmr little millet. With a fixed random seed (2026) the builder samples six accessions per crop, 66 in total, and checks that every gold query returns a non-empty, tie-free result. Each SeedVariety row keeps the real accession number, the holding genebank and the DOI, so every variety can be traced to its public record."));
add(H2("B. Database schema"));
add(P("The database has five tables linked by foreign keys: each seed lot belongs to one variety, and each germination test, storage reading and distribution belongs to one lot. Table IV gives the sizes."));
add(TCAP("Table IV.", "Seed-bank database (66 real accessions, simulated monitoring records, random seed 2026)"));
add(TABLE([1700, 800, 3900, 2900], [
  ["Table", "Rows", "Key fields", "Role"],
  ["SeedVariety", "66", "crop_name, local_name, crop_type, drought_tolerance, accession_number, genebank, doi", "Real ICRISAT accessions (11 crops, 4 crop types)"],
  ["SeedLot", "122", "variety_id, storage_location, quantity, collection_date", "Physical seed batches in 5 locations"],
  ["GerminationTest", "294", "lot_id, test_date, germination_rate", "1–4 viability tests per lot"],
  ["StorageLog", "4,004", "lot_id, recorded_date, temperature, humidity", "Monthly storage readings"],
  ["Distribution", "152", "lot_id, destination, quantity, date", "Seed given to farmer groups"],
], { center: [1] }));
add(AFTER());
add(H2("C. Data generation"));
add(P("Genebanks do not publish per-lot monitoring records, so lots, tests, readings and distributions are simulated. Each accession has one to three lots. Each storage location has a climate profile, from a cold room averaging about 8 °C and 35% relative humidity to an ambient shelf averaging about 20 °C and 54%. A lot's germination rate starts at 88–97% and declines with years in storage, faster in poorer storage:", { keepNext: true }));
add(EQ("g(t) = g_{0} − t · q_{loc} · u − ε,     u ~ U(1.2, 3.2),  ε ~ U(0, 4)", 4));
add(P("where *t* is years since the lot was regenerated and *q*_{loc} a location quality factor (0.4 for Cold Room A, 0.6 for Cold Room B, 1.3 for the village hub, 1.6 for the clay pot store and 2.4 for the ambient shelf). Rates are clipped to 18–99%. Crop type and drought tolerance follow a crop-level rule (millets and sorghum High, pulses and groundnut Medium). Because of noise, a lot can fail one test and pass a later retest, and the reverse: 24 lots now have a latest rate below 75% although an earlier test was 75% or higher. This is exactly why \"most recent test\" logic matters. Fig. 2 shows all 294 tests."));
add(IMG("fig3_germination.png", 600, 290));
add(FCAP("Fig. 2 · germination rate against years in storage, by storage location (lines are least-squares fits)"));
add(H2("D. Benchmark questions"));
add(P("The benchmark has 60 questions. Each has a category, given by the kind of reasoning it needs, and a tier, following the proposal's three complexity levels: Tier 1 uses one table and simple filters, Tier 2 adds grouping or one join, and Tier 3 adds per-lot temporal logic, several joins or combined conditions. Fig. 3 shows the split. Assumptions are stated in the questions and in the schema description: a retest threshold of 75% germination, recommended storage of at most 15 °C and 50% humidity, viable stock defined as quantity above zero with a most recent germination of at least 75%, a reference date of 1 November 2026, and SeedLot.quantity as the stock left after all distributions."));
add(IMG("fig4_benchmark.png", 600, 220));
add(FCAP("Fig. 3 · benchmark questions by category and tier (10 in Tier 1, 21 in Tier 2, 29 in Tier 3)"));
add(TCAP("Table V.", "Example benchmark questions and the SQL features each requires (gold rows on the current database)"));
add(TABLE([1000, 4700, 2800, 900], [
  ["ID", "Question (abridged)", "Required SQL", "Gold rows"],
  ["T1-01", "Crop and local names of highly drought-tolerant varieties", "Filter, two columns", "48"],
  ["T1-03", "Tests in 2026 with germination below 75%", "Date range + threshold", "10"],
  ["DOM-01", "How many lots are out of stock", "COUNT with filter", "1"],
  ["T2-01", "Total quantity per storage location", "GROUP BY + SUM", "5"],
  ["T2-03", "Top 5 lots by out-of-range storage readings", "OR filter, ORDER BY, LIMIT", "5"],
  ["JN-02", "Crops with lots on the Ambient Shelf", "Join + filter", "10"],
  ["TMP-11", "Months of 2026 with average storage temperature above 15 °C", "strftime + GROUP BY + HAVING", "1"],
  ["TMP-14", "Lots with seed distributed in 2026 and the amount", "Date range + GROUP BY", "20"],
  ["T3-01", "Lots whose most recent germination is below 75%", "Correlated MAX subquery", "38"],
  ["T3-02", "Drought-tolerant varieties with viable stock", "3-table join + latest test", "36"],
  ["T3-04", "Varieties with a low result since 2025 and no retest", "Join + NOT EXISTS", "16"],
  ["TMP-05", "Lots that lost more than 20 points between first and latest test", "Self-join on MIN and MAX dates", "18"],
  ["DOM-02", "Lots that are viable stock", "Stock + latest test + threshold", "77"],
  ["DOM-07", "Original quantity of each lot (current stock plus distributed)", "Join + SUM, no double counting", "86"],
  ["AGG-01", "Average germination per crop type", "3-table join + AVG", "4"],
], { center: [3] }));
add(AFTER());
add(P("Four few-shot demonstrations cover a filter, a GROUP BY, the latest storage reading per lot and NOT EXISTS. An automated test checks that no demonstration has the same SQL as a benchmark question or a very similar wording. This check found that one demonstration in the earlier version was a reworded copy of question TMP-01, and it was replaced."));

// VI
add(H1("VI. Evaluation Protocol"));
add(H2("A. Relaxed execution accuracy"));
add(P("Following execution-based evaluation [6], [7], a prediction is scored by its result, not its text. match(*R*, *R*^{*}) is true when (1) *R* and *R*^{*} have the same number of rows, and (2) there is an injective mapping from gold columns to predicted columns such that the multiset of projected rows is equal. Numbers are compared to two decimal places, numeric strings are treated as numbers, and text is compared case-insensitively. Row order, column order, aliases and extra predicted columns are ignored. Automated tests confirm that equivalent formulations match (for example a window function in place of a correlated subquery), while wrong ones do not (for example AND in place of OR, or all tests in place of the latest)."));
add(H2("B. Temporal robust accuracy"));
add(P("A query can match the gold result on one database by coincidence. Temporal robust accuracy (TRA) counts a question as correct only if the prediction matches gold on the benchmark database and on five changed states. Each state is a copy with 14 new germination tests dated after all existing tests (some crossing 75%), six lots emptied and three restocked, three new distributions, six new storage readings, and records dated 2027-02-10 for four lots, as if next year's data had arrived. States where the gold top-k answer has a tie are redrawn. The gold query is the oracle here, so TRA is only used for evaluation, never inside the loop."));
add(H2("C. Metrics"));
add(P("For *N* questions with final result *R*_{i} and gold *R*^{*}_{i}:", { keepNext: true }));
add(EQ("EX = (1/N) Σ_{i} 1[ match(R_{i}, R^{*}_{i}) ]", 5));
add(EQ("TRA = (1/N) Σ_{i} 1[ match on D and on each of the 5 changed states ]", 6));
add(TCAP("Table VI.", "Metrics"));
add(TABLE([2800, 6200], [
  ["Metric", "Definition"],
  ["Execution accuracy (EX)", "Share of questions whose final result matches gold"],
  ["Temporal robust accuracy (TRA)", "Share of questions that also match gold on all five changed states"],
  ["Rule compliance", "Share of final queries with no validator finding (partly circular for the VG methods, so reported as a diagnostic)"],
  ["Successful query rate (SQR)", "Share of questions whose final SQL executes without error"],
  ["Average iterations", "Mean generate-and-execute passes per question"],
  ["Average LLM calls", "Mean LLM calls per question, as a cost measure"],
  ["First-attempt EX", "EX of iteration 1 only; the gap to final EX is the gain from refinement"],
  ["Error reduction", "Questions with any error on the first attempt compared with the final answer, by category"],
]));
add(AFTER());
add(H2("D. Error taxonomy"));
add(P("Execution errors are classified from SQLite messages as syntax error, unknown column, unknown table, ambiguous column, aggregation misuse, invalid or non-SELECT statement, and other. Queries that execute but fail to match gold are labelled wrong result, or wrong result (empty) when they return no rows. Validator findings on the final answers are also counted by category (schema, join, temporal, domain, aggregation)."));
add(H2("E. Evaluating the validator"));
add(P("The validator is evaluated offline, without any LLM. False alarms are counted on the 60 gold queries and on 18 correct rewrites written in other SQL styles (window functions, common table expressions, NOT EXISTS, ORDER BY with LIMIT 1, conditional sums, strftime or BETWEEN for years, USING joins). Detection is measured by mutation testing [15]: 12 operators inject realistic mistakes into the gold queries, such as dropping the latest-test condition, taking the newest test of the whole table, using the earliest test, moving a threshold, turning OR into AND, subtracting distributions from the current stock, and joining on the wrong key. Only mutants that execute and return a different answer from gold are kept, because those are the mistakes that execution feedback would accept."));
add(H2("F. Configuration and statistics"));
add(P("All methods use the same model, temperature 0, database and iteration limit *K* = 4. [Report the provider, model identifier and run dates.] Each configuration is run R = 3 times to measure run-to-run variation, and we report the mean and standard deviation. Accuracies get 95% Wilson confidence intervals. Methods are compared on the same questions with the exact McNemar test [20] on paired correct/incorrect outcomes, with Holm's correction over ten planned comparisons. With 60 questions, one question is 1.7 percentage points overall, so small differences are not treated as conclusive."));

// VII
add(H1("VII. Results"));
add(P("Sections A to D are offline results produced by eval_validator.py and eval_robustness.py; they need no LLM and can be reproduced exactly. Section E is the LLM comparison."));
add(H2("A. False alarms on correct queries"));
add(P("A validator that flags correct queries would push TextGrad away from right answers. On the 60 gold queries and the 18 correct rewrites the validator produced no findings at all (0 false alarms out of 78)."));
add(H2("B. Detection of wrong-but-running queries"));
add(P("The 12 mutation operators produced 105 mutants that execute and return a different answer from gold. Table VII and Fig. 4 show the result. Static rules flagged 104 of them (99%), and with metamorphic tests all 105 (100%) were flagged. The one mutant the rules missed had a reversed threshold direction, and a metamorphic test caught it. Metamorphic tests also failed, independently of the rules, for about half of the latest-test mistakes and for every stock, date-bound and no-retest mistake. For structural mistakes such as a missing GROUP BY no relation applies, and the rules do the work."));
add(TCAP("Table VII.", "Validator evaluation (offline, no LLM)"));
add(TABLE([5600, 1600, 1800], [
  ["Check", "Queries", "Result"],
  ["False alarms on gold queries", "60", "0 (0%)"],
  ["False alarms on correct rewrites in other SQL styles", "18", "0 (0%)"],
  ["Wrong-but-running mutants flagged by static rules", "105", "104 (99%)"],
  ["Wrong-but-running mutants flagged by rules + metamorphic tests", "105", "105 (100%)"],
], { center: [1, 2] }));
add(AFTER());
add(IMG("fig2_validator.png", 600, 309));
add(FCAP("Fig. 4 · mutants flagged by mistake type (number of mutants in brackets)"));
add(P("These figures are optimistic. The rules were refined on this benchmark until the false alarms disappeared, so they describe a development set. A held-out question set written by someone who did not write the rules is needed before they can be read as generalisation."));
add(H2("C. Wrong queries that look right on one database"));
add(P("Nine mutants returned exactly the gold answer on the benchmark database, so ordinary execution accuracy would score them as correct. On the five changed states, five of them diverged from gold (Table VIII): four had dropped a date bound (questions T1-03, TMP-10, TMP-11 and TMP-14) and one had dropped the no-retest condition (T3-04). Today these give the right rows; when next year's records arrive they will not. The validator flagged four of the five without the gold answer. The other four mutants gave the gold answer on every state, so there is no evidence that they are wrong. TRA accepted all 60 gold queries and all 18 correct rewrites."));
add(TCAP("Table VIII.", "Mutants that match gold on the benchmark database"));
add(TABLE([6600, 2400], [
  ["Outcome on the five changed states", "Mutants"],
  ["Diverge from gold (counted correct by EX, rejected by TRA)", "5"],
  ["   of which dropped a date bound", "4"],
  ["   of which dropped the no-retest condition", "1"],
  ["   of which flagged by the validator", "4"],
  ["Same as gold on every state", "4"],
  ["Correct queries (gold and rewrites) rejected by TRA", "0 of 78"],
], { center: [1] }));
add(AFTER());
add(H2("D. Coverage and cost of validation"));
add(P("Table IX shows how often intent extraction activates each question-dependent rule. On the 60 gold queries the validator ran 28 metamorphic tests in total, on 14 questions; the other questions have no applicable relation and are checked by rules alone. Validation took about 6 ms per query on a laptop, which is small next to one LLM call."));
add(TCAP("Table IX.", "Rule activation by intent on the 60 questions"));
add(TABLE([5600, 1600], [
  ["Rule (activated when the question…)", "Questions"],
  ["AGG-GROUP (…asks \"for each\")", "23"],
  ["TEMP-LATEST (…asks for the latest test)", "18"],
  ["DOM-THRESHOLD (…states a germination threshold)", "14"],
  ["AGG-COUNT (…asks \"how many\")", "13"],
  ["TEMP-RANGE (…states a year or date bound)", "12"],
  ["DOM-STOCK (…requires stock)", "6"],
  ["DOM-STORAGE (…mentions storage limits)", "5"],
  ["TEMP-NORETEST (…excludes retested lots)", "2"],
], { center: [1] }));
add(AFTER());
add(H2("E. LLM comparison"));
add(P("Draft note: the tables below are templates. Fill every \"—\" from results/<run>/summary.md and stats.md produced by run_experiments.py with --repeats 3, report the mean over three runs with the standard deviation, and then write the findings paragraph. Do not report numbers from the mock provider or from the earlier run that failed with HTTP 403."));
add(TCAP("Table X.", "Execution accuracy and temporal robust accuracy (%) by method"));
add(TABLE([3000, 1000, 1000, 1000, 1200, 1200], [
  ["Method", "Tier 1", "Tier 2", "Tier 3", "All (EX)", "All (TRA)"],
  ...["Zero-shot", "Few-shot", "Error-retry", "TextGrad", "Validator-retry", "VG-TextGrad (static)", "VG-TextGrad"].map((m) => [m, "—", "—", "—", "—", "—"]),
], { center: [1, 2, 3, 4, 5] }));
add(AFTER());
add(P("[Findings: which method is best overall and per tier; whether VG-TextGrad's gain over TextGrad is concentrated in the temporal and domain questions; McNemar p-values for VG-TextGrad vs TextGrad, vs Validator-retry and vs VG-TextGrad (static).]"));
add(TCAP("Table XI.", "Successful query rate, rule compliance, refinement effort and cost (all tiers)"));
add(TABLE([3000, 1100, 1300, 1400, 1300, 1300], [
  ["Method", "SQR (%)", "Rule comp. (%)", "First-attempt EX (%)", "Avg. iterations", "Avg. LLM calls"],
  ["Zero-shot", "—", "—", "—", "1.00", "1.0"],
  ["Few-shot", "—", "—", "—", "1.00", "1.0"],
  ...["Error-retry", "TextGrad", "Validator-retry", "VG-TextGrad (static)", "VG-TextGrad"].map((m) => [m, "—", "—", "—", "—", "—"]),
], { center: [1, 2, 3, 4, 5] }));
add(AFTER());
add(TCAP("Table XII.", "Questions by error category, first attempt → final answer"));
add(TABLE([3000, 1500, 1500, 1500, 1500], [
  ["Category", "Error-retry", "TextGrad", "Validator-retry", "VG-TextGrad"],
  ...["Syntax error", "Unknown column / table", "Other execution error", "Wrong result", "Wrong result (empty)"].map((c) => [c, "— → —", "— → —", "— → —", "— → —"]),
], { center: [1, 2, 3, 4] }));
add(AFTER());
add(P("The key comparison is the wrong-result row. Error-retry cannot change a query that executes, so any reduction there comes from the evaluator, the validator, or both. The run folder also contains charts of accuracy by tier and by category and of error categories (charts/*.png), which can replace these tables in the final version."));
add(H2("F. Case study: per-lot temporal logic (T3-01)"));
add(P("The question asks for lots whose most recent germination rate is below 75%. The gold query returns 38 lots:"));
add(CODE(["SELECT g.lot_id, g.germination_rate", "FROM GerminationTest g", "WHERE g.test_date = (SELECT MAX(g2.test_date) FROM GerminationTest g2", "                     WHERE g2.lot_id = g.lot_id)", "  AND g.germination_rate < 75;"]));
add(P("A typical wrong query filters every test:"));
add(CODE(["SELECT g.lot_id, g.germination_rate", "FROM GerminationTest g", "WHERE g.germination_rate < 75;"]));
add(P("On the current database this executes and returns 64 rows covering 40 lots. Lots with several failed tests appear more than once, and two lots appear whose newer test passed, so the answer is wrong. Error-retry would accept it because it executes. Without the gold answer, the validator reports two findings:"));
add(BUL("TEMP-LATEST (static rule): \"The question refers to the most recent germination result, but the SQL never selects the latest test per lot.\""));
add(BUL("TEMP-LATEST (metamorphic test MR-LATEST): \"after adding a newer germination test of 90% for every lot of lot '1', the query still returned '1'. The answer should depend only on the latest test.\""));
add(P("In VG-TextGrad these findings stop the loop from passing, and the gradient starts with \"[TEMP-LATEST] Select the most recent germination test separately for each lot before applying any threshold\", which the step folds into the prompt. A second mistake, taking the newest test of the whole table instead of each lot, returns a single row and is caught by TEMP-PERLOT. The two findings above are actual validator output on these queries. [Add a verbatim trace from records.jsonl after the LLM runs, including the actual loss, gradient and prompt diff.]"));

// VIII
add(H1("VIII. Discussion"));
add(P("[Rewrite this section once the LLM results are in. The points below are the analyses the design supports, not findings.]"));
add(lead("Where the validator should matter.", "Tier-3 temporal and domain questions need per-lot logic and combined conditions, which are the errors that execute silently. If VG-TextGrad helps, the gain over TextGrad should appear there, in the wrong-result category and in TRA, not in Tier 1."));
add(lead("Validator vs loop.", "Validator-retry gives the same evidence without TextGrad. If it reaches the same accuracy at lower cost, the evidence matters more than the optimizer; if VG-TextGrad is better, the loss and gradient add value."));
add(lead("Rules vs metamorphic tests.", "VG-TextGrad (static) removes the metamorphic tests. The offline results suggest the rules alone catch most injected mistakes on this benchmark, so the tests may matter mainly for mistakes the rules were not written for."));
add(lead("Evaluator reliability.", "A false FAIL wastes iterations and can damage a correct query; a false PASS stops too early. The veto removes false PASS verdicts when the validator has a finding. Because gold is known offline, both rates can be measured from the traces."));
add(lead("Cost.", "VG-TextGrad adds four calls per refinement and no calls for validation. The useful comparison is accuracy gained per additional call, against error-retry, validator-retry and few-shot."));
add(lead("Transfer.", "Prompt-level mode with the rule memory tests whether lessons such as \"compute the latest test per lot\" improve later questions, or whether question-specific hints accumulate and hurt."));

// IX
add(H1("IX. Limitations and Ethics"));
add(BUL("Simulated monitoring data. Only the 66 accessions are real. Lots, tests, storage readings and distributions are simulated, and real records contain missing values and inconsistent naming that are not modelled."));
add(BUL("Development-set validator figures. The rules and phrase lists were refined on the same 60 questions; a held-out question set is needed."));
add(BUL("Small benchmark, one domain. Sixty questions on one schema limit statistical power, and findings may not transfer to other schemas."));
add(BUL("Rule coverage. The validator only knows the mistakes it has rules and relations for. An unseen kind of mistake passes silently, and rule compliance is partly circular for the VG methods."));
add(BUL("Relaxed matching. Ignoring extra columns can accept an answer with a surplus column; TRA reduces but does not remove such cases."));
add(BUL("Assigned attributes and thresholds. Drought tolerance and crop type follow a crop-level rule, and the 75% retest threshold and storage limits are demonstration values, not official genebank standards [19]."));
add(BUL("Author-written questions and model dependence. Questions and gold SQL were written by the authors, which may introduce bias, and providers retire models, so model identifiers and run dates are reported."));
add(BUL("Ethics and safety. The system is decision support only and makes no agricultural decisions. Model-written SQL runs in a read-only sandbox. Genesys data are used under its terms of use [16], no personal data are involved, and the farmer-group names in the simulated distributions are invented."));

// X
add(H1("X. Conclusion and Future Work"));
add(P("We presented a TextGrad-guided Text-to-SQL pipeline for community seed-bank analytics in which the loss and the gradient are grounded in a validator that needs no reference answer. The validator reads the question's intent, checks the SQL with domain and temporal rules, and tests its behaviour on controlled changes to the data. On a benchmark of 60 questions over real ICRISAT accessions, it raised no false alarm on 78 correct queries and flagged all 105 injected wrong-but-running queries, and temporal robust accuracy exposed five wrong queries that ordinary execution accuracy would score as correct. [Add the one-sentence main LLM result.] Future work will run the seven-method comparison with repeated runs, write a held-out question set with seed-bank practitioners, compare several model sizes, measure evaluator accuracy directly, test whether the rule memory transfers across questions, and use openly licensed monitoring records where available."));

// References
add(H1("References"));
const REFS = [
  ["M. Yuksekgonul, F. Bianchi, J. Boen, S. Liu, Z. Huang, C. Guestrin, and J. Zou, \"TextGrad: Automatic 'differentiation' via text,\" arXiv:2406.07496, 2024. Published as \"Optimizing generative AI by backpropagating language model feedback,\" Nature, vol. 639, pp. 609–616, 2025.", "https://arxiv.org/abs/2406.07496"],
  ["L. Nan, Y. Zhao, W. Zou, N. Ri, J. Tae, E. Zhang, A. Cohan, and D. Radev, \"Enhancing text-to-SQL capabilities of large language models: A study on prompt design strategies,\" in Findings of EMNLP, 2023, pp. 14935–14956.", "https://aclanthology.org/2023.findings-emnlp.996/"],
  ["W. Mao, R. Wang, J. Guo, J. Zeng, C. Gao, P. Han, and C. Liu, \"Enhancing text-to-SQL parsing through question rewriting and execution-guided refinement,\" in Findings of ACL, 2024, pp. 2009–2024.", "https://aclanthology.org/2024.findings-acl.120/"],
  ["R. Sun, S. Ö. Arik, R. Sinha, H. Nakhost, H. Dai, P. Yin, and T. Pfister, \"SQLPrompt: In-context text-to-SQL with minimal labeled data,\" in Findings of EMNLP, 2023, pp. 542–550.", "https://aclanthology.org/2023.findings-emnlp.39/"],
  ["Z. Hong, Z. Yuan, Q. Zhang, H. Chen, J. Dong, F. Huang, and X. Huang, \"Next-generation database interfaces: A survey of LLM-based text-to-SQL,\" arXiv:2406.08426, 2024.", "https://arxiv.org/abs/2406.08426"],
  ["T. Yu et al., \"Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task,\" in Proc. EMNLP, 2018, pp. 3911–3921.", "https://aclanthology.org/D18-1425/"],
  ["J. Li et al., \"Can LLM already serve as a database interface? A BIg bench for large-scale database grounded text-to-SQLs,\" in Proc. NeurIPS, 2023.", "https://arxiv.org/abs/2305.03111"],
  ["R. Zhong, T. Yu, and D. Klein, \"Semantic evaluation for text-to-SQL with distilled test suites,\" in Proc. EMNLP, 2020, pp. 396–411.", "https://aclanthology.org/2020.emnlp-main.29/"],
  ["B. Wang et al., \"MAC-SQL: A multi-agent collaborative framework for text-to-SQL,\" in Proc. COLING, 2025, pp. 540–557.", "https://aclanthology.org/2025.coling-main.36/"],
  ["S. Piao, J. Lee, and S. Park, \"LitE-SQL: A lightweight and efficient text-to-SQL framework with vector-based schema linking and execution-guided self-correction,\" arXiv:2510.09014, 2025.", "https://arxiv.org/abs/2510.09014"],
  ["A. Jain and M. Shrivastava, \"Reflect-SQL: A self-reflection based framework for text-to-SQL,\" arXiv:2609.02944, 2026.", "https://arxiv.org/abs/2609.02944"],
  ["R. Pryzant, D. Iter, J. Li, Y. T. Lee, C. Zhu, and M. Zeng, \"Automatic prompt optimization with 'gradient descent' and beam search,\" in Proc. EMNLP, 2023, pp. 7957–7968.", "https://aclanthology.org/2023.emnlp-main.494/"],
  ["S. Gurajada, E. Kandogan, and S. Rahman, \"Effectiveness of prompt optimization in NL2SQL systems,\" arXiv:2505.20591, 2025.", "https://arxiv.org/abs/2505.20591"],
  ["T. Y. Chen, S. C. Cheung, and S. M. Yiu, \"Metamorphic testing: A new approach for generating next test cases,\" Tech. Rep. HKUST-CS98-01, Hong Kong Univ. of Science and Technology, 1998.", null],
  ["Y. Jia and M. Harman, \"An analysis and survey of the development of mutation testing,\" IEEE Trans. Softw. Eng., vol. 37, no. 5, pp. 649–678, 2011.", null],
  ["Global Crop Diversity Trust, \"Genesys: Plant genetic resources portal,\" ICRISAT (IND002) accession list and terms of use, accessed Nov. 2026.", "https://www.genesys-pgr.org"],
  ["USDA-ARS, \"GRIN-Global: Germplasm Resource Information Network.\"", "https://www.grin-global.org"],
  ["F. R. Hay et al., \"CGIAR genebank viability data reveal inconsistencies in seed collection management,\" Global Food Security, vol. 30, art. 100557, 2021.", "https://doi.org/10.1016/j.gfs.2021.100557"],
  ["FAO, Genebank Standards for Plant Genetic Resources for Food and Agriculture, rev. ed. Rome, 2014.", "http://www.fao.org/3/a-i3704e.pdf"],
  ["Q. McNemar, \"Note on the sampling error of the difference between correlated proportions or percentages,\" Psychometrika, vol. 12, no. 2, pp. 153–157, 1947.", null],
  ["OpenAI, \"gpt-oss-120b & gpt-oss-20b model card,\" arXiv:2508.10925, 2025.", "https://arxiv.org/abs/2508.10925"],
];

REFS.forEach(([t, u]) => {
  add(new Paragraph({ numbering: { reference: "refs", level: 0 }, children: runs(t), spacing: { after: u ? 0 : 120, line: 280 } }));
  if (u) add(new Paragraph({ children: [new TextRun({ text: u, font: FONT, color: INK })], indent: { left: 720 }, spacing: { after: 120 } }));
});

// ============================================================================================ document
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
  new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], font: FONT, size: 12, color: "6B6B6B" })] })] });
const doc = new Document({
  creator: "Gayathri Priya V, Gonu Guntla Hema Kowshik, Bhavin G Kamat",
  title: "TextGrad-Guided Text-to-SQL for Community Seed-Bank Viability and Climate-Resilience Analytics",
  styles: {
    default: { document: { run: { font: FONT, size: 24, color: INK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 33, color: INK }, paragraph: { spacing: { before: 360, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 27, color: INK }, paragraph: { spacing: { before: 200, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "refs", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 400 } } } }] },
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  ] },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1009, right: 1082, bottom: 1183, left: 1080, header: 314, footer: 302 } } },
    footers: { default: footer }, children: C }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(process.argv[2] || "paper.docx", b); console.log("ok"); });
