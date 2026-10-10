"""What the setup offers around "What do you want to learn?": who she is
(asked once, so later questions can be fewer), the broad directions for
someone who doesn't know yet (a direction, then a narrower one, and for some
a third), and the goals that fit who she is.

Pure data and small functions, no Streamlit."""

# who she is: asked once in the setup (skippable only by saying she knows
# exactly what she wants); kept with her preferences (prefs "identity")
IDENTITIES = ("Student", "Working adult", "Changing careers", "Retired", "Learning for the love of it")

# for someone who doesn't know yet: direction → narrower → (for some) narrower still
DIRECTIONS = {
    "Languages": {
        "English": ("Everyday conversation", "Grammar that makes sense", "Reading and writing", "Exam preparation"),
        "Japanese": ("Travel phrases", "Hiragana and katakana", "Everyday conversation"),
        "Korean": ("Hangul and pronunciation", "Everyday conversation"),
        "Writing well in Chinese": (),
        "Another language": (),
    },
    "Math": {
        "Everyday math": (),
        "Statistics": ("Reading charts and numbers", "Probability", "Statistics for a course"),
        "Algebra and functions": (),
        "Logical thinking": (),
    },
    "Natural science": {
        "Physics": ("How everyday things work", "Energy and motion", "Light and sound"),
        "Chemistry": (),
        "Biology": ("The human body", "Evolution", "Plants and animals"),
        "Earth and space": ("Weather and climate", "The night sky", "Volcanoes and earthquakes"),
        "Health and the body": (),
    },
    "Society": {
        "History": ("Ancient civilizations", "The modern world", "History of a country", "How people used to live"),
        "Psychology": ("Why people do what they do", "Habits and motivation", "Emotions and the mind"),
        "Economics": ("How money and markets work", "Behavioral economics", "Personal finance"),
        "Politics and society": (),
        "Philosophy": ("Big questions", "Ethics: how to live", "Great thinkers"),
    },
    "Arts": {
        "Art and painting": ("Looking at paintings", "Art history", "Drawing basics"),
        "Music": ("Reading music", "Music history", "Learning an instrument"),
        "Film and photography": (),
        "Design": (),
        "Literature": ("Great novels", "Poetry"),
    },
    "Technology": {
        "Programming": ("Python for beginners", "Building a website", "Automating everyday tasks"),
        "Artificial intelligence": ("What AI is and how it works", "Using AI tools well"),
        "Internet and security": ("Staying safe online", "How the internet works"),
        "Computer basics": (),
        "Technology trends": (),
    },
}

# what she wants it for: offered by who she is (each list ends with her own words)
PURPOSES = {
    "Student": ("For an exam", "To keep up in class", "For a project or essay"),
    "Working adult": ("Useful at work", "For a career move", "Out of curiosity"),
    "Changing careers": ("To move into a new field", "To prepare for interviews", "To build a first project"),
    "Retired": ("Out of curiosity", "To keep my mind active", "For a trip or a hobby"),
    "Learning for the love of it": ("Out of curiosity", "To understand the world better", "For a hobby"),
}
# who she is → the group of ideas shown first under "What do you want to learn?"
# (coach/paths.SUGGESTIONS)
IDEAS = {"Student": "Study", "Working adult": "Work and money", "Changing careers": "Work and money",
         "Retired": "Curiosity", "Learning for the love of it": "Curiosity"}
GENERAL_PURPOSES = ("Useful at work or study", "Out of curiosity", "For a hobby or a trip")
ALL_OF_IT = "To learn all of it"          # the goal of someone who skips this question


def purposes(identity) -> tuple:
    """The goals offered to her (general ones when she didn't say who she is)."""
    return PURPOSES.get(identity, GENERAL_PURPOSES)


def narrower(path: list):
    """The choices one level below `path` (a direction, then a narrower one),
    or () when there is nothing narrower: the path is then her topic."""
    if not path:
        return tuple(DIRECTIONS)
    level = DIRECTIONS.get(path[0])
    if level is None:
        return ()
    if len(path) == 1:
        return tuple(level)
    if len(path) == 2:
        return tuple(level.get(path[1], ()))
    return ()


def topic_of(path: list) -> str:
    """Her topic in words, from what she picked: "Statistics: Probability"."""
    picked = [p for p in path[1:] if p]          # (the broad direction itself isn't a topic)
    if len(picked) >= 2:
        return f"{picked[0]}: {picked[1]}"
    return picked[0] if picked else (path[0] if path else "")
