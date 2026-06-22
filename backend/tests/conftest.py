from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def curso_origem_pdf() -> Path:
    return FIXTURES / "curso_origem.pdf"


@pytest.fixture
def curso_destino_pdf() -> Path:
    return FIXTURES / "curso_destino.pdf"


@pytest.fixture
def historico_pdf() -> Path:
    return FIXTURES / "historico_arthur.pdf"
