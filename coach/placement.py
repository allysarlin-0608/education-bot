"""The placement check: five questions on a subject, from its first
lessons to well into the syllabus, that set where the subject starts.

It is only a way to choose a starting level. Nothing here touches the
learning log: no entry, no lesson, no quiz record, no progress.

0–2 right: Beginner · 3–4: Intermediate · 5: Advanced."""

COUNT = 5

# topic -> five (question, options, index of the right option), easiest first
QUESTIONS = {
    "philosophy": [
        ("Which branch of philosophy asks what we can know, and how?",
         ["Ethics", "Epistemology", "Aesthetics", "Metaphysics"], 1),
        ("An argument whose conclusion must be true if its premises are true is called…",
         ["Valid", "Persuasive", "Inductive", "Circular"], 0),
        ("Who wrote the Meditations, a Roman emperor's private Stoic notes to himself?",
         ["Seneca", "Epictetus", "Marcus Aurelius", "Epicurus"], 2),
        ("Kant's categorical imperative asks you to act only on a rule that…",
         ["produces the most happiness for the most people", "a virtuous person would follow",
          "you could will to become a universal law", "everyone in society has agreed to"], 2),
        ("In Sartre's phrase \"existence precedes essence\", what comes first?",
         ["Our nature, which our choices then express", "That we exist; we make what we are by choosing",
          "God's plan for each person", "The society that shapes us"], 1),
    ],
    "cosmos": [
        ("Which planet is the largest in the solar system?",
         ["Saturn", "Jupiter", "Neptune", "Earth"], 1),
        ("What causes the Moon's phases?",
         ["Earth's shadow falling on the Moon", "How much of its sunlit half we see from Earth",
          "The Moon's distance from Earth changing", "Clouds of dust passing in front of it"], 1),
        ("A light-year is a measure of…",
         ["Time", "Brightness", "Distance", "Speed"], 2),
        ("The transit method finds exoplanets by watching for…",
         ["A star wobbling towards and away from us", "A small, regular dip in a star's brightness",
          "Light bent by the planet's gravity", "The planet's own glow"], 1),
        ("On the Hertzsprung–Russell diagram, where do most stars, the Sun included, lie?",
         ["Among the red giants", "Among the white dwarfs", "On the main sequence", "Among the supergiants"], 2),
    ],
    "investing": [
        ("Owning a share of stock means you own…",
         ["A small part of a company", "A loan you made to a company", "A guaranteed return",
          "A part of the stock exchange"], 0),
        ("In general, a higher expected return comes with…",
         ["Lower risk", "No change in risk", "Higher risk", "A government guarantee"], 2),
        ("A price-to-earnings (P/E) ratio compares a share's price with the company's…",
         ["Dividend per share", "Earnings per share", "Revenue per share", "Debt per share"], 1),
        ("When interest rates rise, the prices of existing bonds usually…",
         ["Rise", "Stay the same", "Fall", "Double"], 2),
        ("Rebalancing a portfolio means…",
         ["Moving everything into cash when markets fall", "Buying more of whatever has risen most",
          "Trimming what has grown and adding to what has lagged, back to your target mix",
          "Moving your account to a cheaper broker"], 2),
    ],
    "business": [
        ("A value proposition describes…",
         ["Why a customer would choose your product", "The company's legal structure",
          "How much each founder owns", "Where the business is based"], 0),
        ("A minimum viable product (MVP) is built to…",
         ["Launch with every feature finished", "Test your key assumptions with real customers, cheaply",
          "Impress investors with its design", "Replace talking to customers"], 1),
        ("Break-even is the point where…",
         ["Revenue doubles", "Total revenue equals total costs", "Fixed costs reach zero",
          "Cash flow turns negative"], 1),
        ("A profitable business can still run out of money because…",
         ["Profit isn't the same as cash arriving when the bills are due", "Profit is always taxed away",
          "Profitable companies can't borrow", "Revenue is counted twice"], 0),
        ("In unit economics, the LTV:CAC ratio compares…",
         ["Long-term debt with current assets", "Labour costs with capital costs",
          "What a customer is worth over time with what it costs to win them",
          "Lifetime revenue with annual taxes"], 2),
    ],
    "fashion": [
        ("Which of these fibres comes from a plant?",
         ["Silk", "Wool", "Linen", "Polyester"], 2),
        ("A garment's care label tells you…",
         ["Where its fibre was grown", "How to wash, dry and iron it", "What it cost to make",
          "Its size in every country"], 1),
        ("Denim is usually woven as a…",
         ["Plain weave", "Satin", "Knit", "Twill"], 3),
        ("Viscose (rayon) is best described as…",
         ["A synthetic fibre made from oil", "A natural animal fibre",
          "A regenerated fibre made from wood pulp", "A blend of cotton and polyester"], 2),
        ("Cutting a woven fabric \"on the bias\" means cutting it…",
         ["Along the selvedge", "At 45° to the grain, so it drapes and gives more",
          "Across the weft only", "With pinking shears"], 1),
    ],
    "jewelry": [
        ("24-karat gold is…",
         ["Pure gold", "Half gold", "Gold-plated silver", "White gold"], 0),
        ("The 4Cs of a diamond are carat, colour, clarity and…",
         ["Cost", "Cut", "Crystal", "Cleavage"], 1),
        ("Ruby and sapphire are both varieties of…",
         ["Beryl", "Quartz", "Corundum", "Spinel"], 2),
        ("Sterling silver is…",
         ["Pure silver", "92.5% silver, usually alloyed with copper", "Silver-plated brass",
          "Half silver, half nickel"], 1),
        ("A gem's hardness on the Mohs scale is its resistance to…",
         ["Breaking from a blow", "Heat", "Scratching", "Acids"], 2),
    ],
    "free": [
        ("What do plants take in from the air to make food by photosynthesis?",
         ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], 1),
        ("When demand for something rises and its supply stays the same, its price usually…",
         ["Falls", "Stays fixed", "Rises", "Disappears"], 2),
        ("Which civilisation built Machu Picchu?",
         ["The Aztecs", "The Maya", "The Inca", "The Olmecs"], 2),
        ("A stretch of DNA that carries the code for a trait is called a…",
         ["Cell", "Gene", "Protein", "Ribosome"], 1),
        ("Confirmation bias is the tendency to…",
         ["Favour information that fits what you already believe", "Trust the first number you hear",
          "Overrate your own skill", "Do what the crowd does"], 0),
    ],
}


def questions(topic: str) -> list:
    return QUESTIONS[topic]


def score(topic: str, answers: list) -> int:
    """How many of the five she got right (unanswered counts as wrong)."""
    return sum(1 for (_, _, right), a in zip(QUESTIONS[topic], answers) if a == right)


def level_for(correct: int) -> str:
    if correct >= 5:
        return "Advanced"
    if correct >= 3:
        return "Intermediate"
    return "Beginner"


def answered(answers: list) -> int:
    """How many questions she has answered so far (in order)."""
    return sum(1 for a in answers[:COUNT] if isinstance(a, int))
