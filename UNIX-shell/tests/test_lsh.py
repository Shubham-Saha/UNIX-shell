from datetime import datetime
from os import mkdir, setsid, killpg, getpgid
from pathlib import Path
from signal import SIGINT
from subprocess import run, PIPE, Popen, TimeoutExpired
from tempfile import gettempdir
from time import sleep, time
import unittest

from HTMLTestRunner.runner import HTMLTestRunner
from psutil import Process as ProcessInfo


class TestLsh(unittest.TestCase):

    lsh: Path

    @classmethod
    def setUpClass(cls) -> None:
        r"""
        Builds lsh before executing any test case
        """
        code_dir = Path.joinpath(Path(__file__).parent.parent, "code")
        build_dir = cls.make_tmp_dir()
        run(["cmake", "-B", build_dir, "-S", code_dir], check=True)
        run(["cmake", "--build", build_dir], check=True)
        cls.lsh = build_dir.joinpath("lsh")

    @staticmethod
    def make_tmp_dir() -> Path:
        tmp_dir = Path(gettempdir()).joinpath("test_lab1_" + str(time()))
        mkdir(tmp_dir)
        return tmp_dir

    @staticmethod
    def make_test_txt(cwd: Path):
        with open(cwd.joinpath("test.txt"), "w") as f:
            f.write("hello")

    def check_for_zombies(self, lsh_pid: int):
        lsh_info = ProcessInfo(pid=lsh_pid)
        self.assertEqual([], lsh_info.children(), msg=f"Zombies!")

    def check_test_txt(self, out: Path):
        try:
            with open(out, "r") as f:
                content = f.readlines()
            self.assertListEqual(content, ["hello\n"], msg="Redirected output was not in file")
        except FileNotFoundError:
            self.assertTrue(out.exists(), msg="Failed to detect output file")

    def run_cmd(self, cmd: str, cwd: Path = None, check_for_zombies: bool = False) -> str:
        lsh = Popen(str(self.lsh), stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=cwd, preexec_fn=setsid)
        lsh.stdin.write(f"{cmd}\n".encode())
        lsh.stdin.flush()

        if check_for_zombies:
            self.check_for_zombies(lsh.pid)

        # Puts EOF in stdin and thus lsh will break main loop and return
        out, err = lsh.communicate()

        self.assertEqual("", err.decode())
        self.assertEqual(0, lsh.returncode, msg=f"Failed to execute cmd: {cmd}")

        return out.decode()

    def test_exit(self):
        r"""
        exit
        """
        lsh = Popen(str(self.lsh), stdin=PIPE, stdout=PIPE, stderr=PIPE, preexec_fn=setsid)
        lsh.stdin.write("exit\n".encode())
        lsh.stdin.flush()

        # wait for max 3 seconds for lsh to exit
        try:
            lsh.wait(3)
        except TimeoutExpired:
            self.assertTrue(False, msg="It looks like you don't have an implementation "
                                       "for the build-in command exit")

        self.assertEqual(0, lsh.returncode, msg="lsh should return 0 after executing exit")

    def test_date(self):
        r"""
        Run "date" and then check if the current year appears in stdout
        """
        current_year = str(datetime.now().year)
        self.assertIn(current_year, self.run_cmd(cmd="date"))

    def test_output_redirection(self):
        r"""
        echo Hello > ./hello.txt
        """
        cwd = self.make_tmp_dir()
        out = cwd.joinpath("hello.txt")

        self.run_cmd(cmd="echo hello > ./hello.txt", cwd=cwd)

        self.check_test_txt(out)

    def test_input_redirection(self):
        r"""
        grep el < ./hello.txt
        """
        cwd = self.make_tmp_dir()
        self.make_test_txt(cwd)

        out = self.run_cmd(cmd="grep el < ./test.txt", cwd=cwd)

        self.assertIn("hello", out)

    def test_in_and_out_redirection(self):
        r"""
        Make test.txt and then "grep hello < test.txt > test_out.txt"
        """
        cwd = self.make_tmp_dir()
        self.make_test_txt(cwd)

        out = cwd.joinpath("test_out.txt")

        _ = self.run_cmd(cmd="grep hello < test.txt > test_out.txt", cwd=cwd)

        self.check_test_txt(out)

    def test_cd(self):
        r"""
        Expect to find test.txt after "cd ./test"
        """
        tmp_dir = self.make_tmp_dir()

        with open(tmp_dir.joinpath("hello.txt"), "w") as f:
            f.write("")

        cwd = tmp_dir.parent

        out = self.run_cmd(cmd=f"cd {tmp_dir}\nls", cwd=cwd)

        # Check if ls output has hello.txt to verify that cd works
        self.assertIn("hello.txt", out)

    def test_echo_rev(self):
        r"""
        Execute "echo ananab | rev" and expect to find banana in the output
        """
        out = self.run_cmd(cmd='echo ananab | rev', check_for_zombies=True)
        self.assertIn("banana", out)

    def test_echo_grep_wc(self):
        r"""
        echo hello world | grep hello | wc -w
        """
        out = self.run_cmd(cmd="echo hello world | grep hello | wc -w\n", check_for_zombies=True)
        self.assertIn("2", out)

    def test_bg_and_fg(self):
        r"""
        Execute "sleep 3 &" and then "echo Hello"
        """
        lsh = Popen(str(self.lsh), stdin=PIPE, stdout=PIPE, stderr=PIPE, preexec_fn=setsid)
        lsh.stdin.write("sleep 3 &\n".encode())
        lsh.stdin.flush()

        # Give lsh some time to start and invoke the cmd
        sleep(1)

        # Check if bg process started
        lsh_info = ProcessInfo(pid=lsh.pid)
        self.assertEqual(1, len(lsh_info.children()), msg="Could not detect bg process")

        # Execute a foreground command
        lsh.stdin.write("echo hello\n".encode())
        lsh.stdin.flush()

        # Wait for background command to complete
        sleep(3)

        self.check_for_zombies(lsh.pid)

        # Closes pipes and allows process to terminate gracefully
        out, err = lsh.communicate()

        # Check that foreground command completed
        self.assertIn("hello\n", out.decode())
        self.assertEqual(0, lsh.returncode, msg=f"This should return 0: {err}")

    def test_CTRL_C(self):
        r"""
        Simulate pressing CTRL-C while "sleep 60"
        """
        lsh = Popen(str(self.lsh), stdin=PIPE, stdout=PIPE, stderr=PIPE, preexec_fn=setsid)
        lsh.stdin.write("sleep 60\n".encode())
        lsh.stdin.flush()

        # Give lsh some time to start and invoke the cmd
        sleep(1)

        # Simulate pressing CTRL-C by sending SIGINT to the entire lsh process group
        killpg(getpgid(lsh.pid), SIGINT)

        self.check_for_zombies(lsh.pid)

        # Closes pipes and allows process to terminate gracefully
        _, err = lsh.communicate()
        self.assertEqual(0, lsh.returncode, msg=f"This should return 0: {err}")

    def test_CTRL_C_with_fg_and_bg(self):
        r"""
        Execute "sleep 60 &" then "sleep 60" and then simulate pressing Ctrl-C
        """
        lsh = Popen(str(self.lsh), stdin=PIPE, stdout=PIPE, stderr=PIPE, preexec_fn=setsid)
        lsh.stdin.write("sleep 60 &\n".encode())
        lsh.stdin.flush()

        sleep(1)

        # Store pid of background process
        lsh_info = ProcessInfo(pid=lsh.pid)
        self.assertEqual(1, len(lsh_info.children()), msg="I did not expect to see more than 1 child processes "
                                                          "after executing a background command")
        bg_pid = lsh_info.children()[0]

        # Start foreground process
        lsh.stdin.write("sleep 60\n".encode())
        lsh.stdin.flush()
        sleep(1)

        self.assertEqual(2, len(lsh_info.children()), msg="You do not seem to support a foreground process "
                                                          "and a background process at the same time")

        # Simulate pressing "Ctrl-C" by sending SIGINT to the entire lsh process group
        killpg(getpgid(lsh.pid), SIGINT)
        sleep(1)

        self.assertEqual(1, len(lsh_info.children()), msg="There should be only one child process after Ctrl+C")
        self.assertEqual(bg_pid, lsh_info.children()[0], msg="You should not have terminated the background process")

        # Puts EOF in stdin and thus lsh will break main loop and return
        _, _ = lsh.communicate("exit".encode())

if __name__ == "__main__":
    unittest.main(testRunner=HTMLTestRunner(report_name="test-lsh", open_in_browser=True, description="Lab 1 tests"))
