from automation.answer_format import infer_answer_format, normalize_numeric_answer


def test_infer_number_from_label():
    assert infer_answer_format("How many years of Python experience do you have?", "text") == "number"
    assert infer_answer_format("What is your expected CTC?", "text") == "number"
    assert infer_answer_format("Tell us about yourself", "text") == "text"


def test_normalize_numeric_strips_prose():
    assert normalize_numeric_answer("Years of Java?", "I have 5 years of professional Java experience.") == "5"
    assert normalize_numeric_answer("Expected salary", "1200000 INR per annum") == "1200000"


def test_input_type_number():
    assert infer_answer_format("Unknown field", "number") == "number"
