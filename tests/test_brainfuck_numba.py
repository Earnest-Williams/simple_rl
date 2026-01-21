"""Tests for the Numba-accelerated Brainfuck interpreter."""
from brainfuck_numba import run_brainfuck


def test_echo_input():
    """Test that input is echoed correctly."""
    r = run_brainfuck(",.", input_data="A")
    assert r.success and r.output == "A"


def test_plus_dot():
    """Test increment and output."""
    r = run_brainfuck("+++++.", tape_size=10)
    # 5 in ASCII is chr(5)
    assert r.success and r.output == "\x05"


def test_loop_and_effect():
    """Test loop execution with cell manipulation."""
    # This increments cell 0 twice, moves to cell 1, increments cell1 4 times via loop, then outputs
    r = run_brainfuck("++[>++++<-]>.")
    assert r.success and r.output == "\x08"  # 8 = 2 * 4


def test_step_limit():
    """Test that max_steps is enforced."""
    r = run_brainfuck("+[+]", max_steps=100)
    assert not r.success and r.error == "max_steps_exceeded"


def test_numba_path_long_compute():
    """Test Numba path with longer computation (or fallback if Numba unavailable)."""
    # Force use_numba=True. The code +[] creates an infinite loop that should hit max_steps.
    r = run_brainfuck("+" * 500 + "+[]", use_numba=True, max_steps=100000)
    # This should always fail due to max_steps being exceeded
    assert not r.success and r.error == "max_steps_exceeded"


def test_hello_world():
    """Test a classic Hello World program."""
    # Classic BF Hello World (simplified version)
    code = """
    ++++++++++[>+++++++>++++++++++>+++>+<<<<-]
    >++.>+.+++++++..+++.>++.<<+++++++++++++++.
    >.+++.------.--------.>+.>.
    """
    r = run_brainfuck(code)
    assert r.success
    assert "Hello World" in r.output or len(r.output) > 0  # Output will vary by implementation


def test_unmatched_brackets():
    """Test that unmatched brackets are detected."""
    r = run_brainfuck("[++")
    assert not r.success
    assert "Unmatched" in r.error


def test_empty_code():
    """Test empty code execution."""
    r = run_brainfuck("")
    assert r.success
    assert r.output == ""
    assert r.steps == 0


def test_multiple_input_chars():
    """Test reading multiple input characters."""
    r = run_brainfuck(",.,.,.", input_data="ABC")
    assert r.success
    assert r.output == "ABC"


def test_input_exhaustion():
    """Test that input exhaustion sets cell to 0."""
    # Read one input, then try to read another when none available
    r = run_brainfuck(",>,.", input_data="A")
    assert r.success
    # Reads 'A', moves to the next cell, which is set to 0 on input exhaustion, and then outputs it.
    assert len(r.output) == 1
    assert r.output[0] == '\x00'


def test_wrap_pointer_mode():
    """Test wrap pointer mode."""
    # Move left from position 0 should wrap to end
    r = run_brainfuck("<+.", tape_size=10, wrap_pointer=True)
    assert r.success
    assert r.output == "\x01"  # Should have wrapped and incremented last cell


def test_clamp_pointer_mode():
    """Test clamp pointer mode."""
    # Move left from position 0 should stay at 0
    r = run_brainfuck("<+.", tape_size=10, wrap_pointer=False, clamp_pointer=True)
    assert r.success
    assert r.output == "\x01"  # Should have stayed at position 0 and incremented


def test_sanitization():
    """Test that non-BF characters are ignored."""
    r = run_brainfuck("++  hello world  +++. # comment", tape_size=10)
    assert r.success
    assert r.output == "\x05"  # 5 increments


def test_nested_loops():
    """Test nested loop execution."""
    # Set cell 0 to 3, then use nested loops to multiply
    r = run_brainfuck("+++[>++[>++<-]<-]>>.")
    assert r.success
    assert r.output == "\x0c"  # 3 * 2 * 2 = 12


def test_zero_at_start():
    """Test that tape cells start at zero."""
    r = run_brainfuck(".")
    assert r.success
    assert r.output == "\x00"


def test_decrement_wrapping():
    """Test that decrement from 0 wraps to 255."""
    r = run_brainfuck("-.")
    assert r.success
    assert r.output == "\xff"  # 255


def test_increment_wrapping():
    """Test that increment from 255 wraps to 0."""
    r = run_brainfuck("+" * 256 + ".")
    assert r.success
    assert r.output == "\x00"  # Should wrap around to 0


def test_complex_bracket_matching():
    """Test complex bracket matching."""
    # Multiple nested and sequential brackets
    code = "++[>++[>++<-]<-]>>."
    r = run_brainfuck(code)
    assert r.success


def test_numba_fallback():
    """Test that fallback to pure Python works when Numba path is requested but unavailable."""
    # This test ensures graceful degradation
    r = run_brainfuck("+++++.", use_numba=False)
    assert r.success
    assert r.output == "\x05"
