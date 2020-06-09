"""
Common code between the autograder and test kit.
"""

import sys
import os
import re
import json
import shutil
import subprocess
try: 
    from itertools import zip_longest
except ImportError: # need to support ancient python 2.4 on login.oit.duke.edu by backporting this function
    from itertools import repeat
    def zip_longest(*args, **kwargs):
        fillvalue=kwargs.get('fillvalue',None)
        # zip_longest('ABCD', 'xy', fillvalue='-') --> Ax By C- D-
        iterators = [iter(it) for it in args]
        num_active = len(iterators)
        if not num_active:
            return
        while True:
            values = []
            for i, it in enumerate(iterators):
                try:
                    value = next(it)
                except StopIteration:
                    num_active -= 1
                    if not num_active:
                        return
                    iterators[i] = repeat(fillvalue)
                    value = fillvalue
                values.append(value)
            yield tuple(values)
import xml.etree.ElementTree as ET

# Set test case timeout to 10 seconds (can be overridden by settings)
TEST_CASE_TIMEOUT_DEFAULT = 10

VALID_TEST_MODES = ["exe", "spim", "logisim"]
VALID_DIFF_TYPES = ["normal", "float"]

MB = 1000000

class TextColors:
    """
    Colors for use in print.
    """
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    END = "\033[0m"

try:
    from subprocess import DEVNULL
except ImportError: #old python 2.4 on login.oit.duke.edu doesnt have this. i make a new one
    DEVNULL = open("/dev/null","w")
    
# wrapper for subprocess.check_call to include timeout if and only if python version is 3.x (ugly hack to support python 2 and 3 at same time)
def my_check_call(args, stdin=None, stdout=None, stderr=None, shell=False, timeout=None):
    if sys.version_info[0]==2: # python 2.x has no timeout support
        return subprocess.check_call(args,
                                     stdin=stdin,
                                     stdout=stdout,
                                     stderr=stdout,
                                     shell=shell)
    elif sys.version_info[0]==3:
        return subprocess.check_call(args,
                                     stdin=stdin,
                                     stdout=stdout,
                                     stderr=stdout,
                                     timeout=timeout,
                                     shell=shell)
    else:
        raise Exception("Unrecognized python version")

# java virtual machine choice is a carnival of trash -- this function tries to find the best java for our task
def find_java():
    debug=False # if true, this function prints details of the search to stdout
    
    # collect choices of possible javas
    choices = ['/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/bin/java'] # mac hides their java here, outside of PATH. Thanks, mac.
    choices += subprocess.Popen(["which","-a","java"],stdout=subprocess.PIPE).stdout.read().decode('utf-8').strip().split("\n") # find the PATH based ones
    if debug:
        print("Choices: %s"%choices)
    first_found = None  # note the first java we find that exists
    first_found_version = None
    best_found = None   # note the java that matches the known good version number
    best_found_version = None
    for java in choices:
        # either non-existent or non-executable? skip
        if not os.access(java, os.X_OK): 
            if debug:
                print("%s: not a valid executable" % java)
            continue
            
        # get the version. the decode() stuff and b"\n" is a tapdance to work on both python2 and python3
        pp = subprocess.Popen([java,"-version"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        version_str = pp.stdout.read().strip() + b"\n" + pp.stderr.read().strip() # eat both stdout and stderr, because who knows which it prints to in each version
        version_str = version_str.decode('utf-8')
        version_match = re.search(r'.* version "([^"]+)"',version_str)
        
        # if we can't even parse a version, that's a bad sign. skip it
        if not version_match:
            if debug:
                print("%s: couldn't parse version output" % java)
            continue
        
        version = version_match.group(1)
        if debug:
            print("%s: %s" % (java,version))
        
        if not first_found: 
            first_found = java
            first_found_version = version
            
        # i've seen the logisim cli work with java 1.6, 1.7, and 1.8, so we prefer those. 
        if re.match(r'1\.[678]\.',version):
            best_found = java # this matches the versions i've seen work
            best_found_version = version
    if best_found:
        if debug:
            print("Choosing %s (%s, compatible)" % (best_found,best_found_version))
        return best_found
    if first_found:
        if debug:
            print("Choosing %s (%s, possibly incompatible)" % (first_found,first_found_version))
        return first_found
    if debug:
        print("Giving up and choosing generic 'java'")
    return 'java' # just use the one in the path and pray

# **Attempt** to find modulus operator use in C programs (doesn't fully parse, so can be fooled, but should be good enough)    
def modulus_used(suite_name):
    filename = "%s.c" % suite_name
    myFile = open(filename,"r")
    str1 = myFile.read() # slurp whole file
    myFile.close()
    str1 = re.sub('\".*\"'," ",str1) # eliminate quoted strings
    str1 = re.sub('//.*'," ",str1)  # eliminate one-line comments
    pattern = re.compile('/\\*.*?\\*/', flags=re.DOTALL) # eliminte multi-line comments
    str1 = re.sub(pattern," ",str1)
    return '%' in str1 # if % still remains, we're probably using it as mod operator


"""
Take a function that modifies a file stream's lines and apply it to edit the given file in-place, with an optional backup.
"""
def apply_file_filter(custom_filter, filename, backup_filename=None):
    """
    Apply a file filter.
    """
    if backup_filename:
        shutil.copy(filename, backup_filename)
    fp_src = open(backup_filename, "r")
    fp_dst = open(filename, "w")
    for line in custom_filter(fp_src):
        fp_dst.write(line)
    fp_src.close()
    fp_dst.close()

# remove lines from logisim_cli output that describe blank probes
# this allows students to use probes for debugging without breaking the tester
def logisim_strip_blank_probes(filename):
    def filter_logisim_strip_blank_probes(stream):
        for line in stream:
            if not re.search(r'(probe         |/ )',line):
                yield line

    apply_file_filter(filter_logisim_strip_blank_probes, filename, filename + ".orig")

# Remove spim headers and colon-terminated prompts
def spim_clean(filename):
    def filter_remove_prompts(stream):
        """
        Filter prompts for SPIM.
        """
        for line in stream:
            line = re.sub(r".*:[ \t]*", "", line)
            if re.search(r"\S", line):
                yield line

    def filter_spim(stream):
        """
        Filter SPIM specific headers.
        """
        header_line_prefixes = [
            "SPIM Version",
            "Copyright 1990-",
            "All Rights",
            "See the file README",
            "Loaded:"
        ]
        for i, line in enumerate(stream):
            if i < len(header_line_prefixes) and any(line.startswith(prefix) for prefix in header_line_prefixes):
                continue
            yield line
            
    # compose the two filters above
    def filter_remove_spim_and_prompts(stream):
        return filter_remove_prompts(filter_spim(stream))

    apply_file_filter(filter_remove_spim_and_prompts, filename, filename + ".orig")


class TestOutput:
    """
    Test case output and metadata.
    """
    def __init__(self,
                 name,
                 score,
                 max_score,
                 diff,
                 actual,
                 exit_status_non_zero,
                 exit_status_non_zero_penalty,
                 valgrind_memory_error,
                 valgrind_memory_error_penalty,
                 is_valgrind,
                 is_segfault,
                 visibility,
                 disallowed_components=None,
                 disallowed_components_penalty=1.0):
        self.name = name
        self.score = score
        self.max_score = max_score
        if sys.getsizeof(diff) > MB:
            self.diff_truncated = True
            self.diff = diff[0 : 5000]
        else:
            self.diff_truncated = False
            self.diff = diff
        if sys.getsizeof(actual) > MB:
            self.actual_truncated = True
            self.actual = actual[0 : 5000]
        else:
            self.actual_truncated = False
            self.actual = actual
        self.exit_status_non_zero = exit_status_non_zero
        self.exit_status_non_zero_penalty = exit_status_non_zero_penalty
        self.valgrind_memory_error = valgrind_memory_error
        self.valgrind_memory_error_penalty = valgrind_memory_error_penalty
        self.is_valgrind = is_valgrind
        self.is_segfault = is_segfault
        self.visibility = visibility
        self.disallowed_components = disallowed_components
        self.disallowed_components_penalty = disallowed_components_penalty

    def to_dictionary(self):
        """
        Convert test output to dictionary for json output.
        """
        output = ""
        if self.exit_status_non_zero:
            penalty = "no penalty applied"
            if self.exit_status_non_zero_penalty < 1:
                penalty = "%d%% penalty applied" % ((1 - self.exit_status_non_zero_penalty) * 100)
            output += "Exit status non zero! (%s)\n" % (penalty)
        if self.valgrind_memory_error and self.is_valgrind:
            if self.valgrind_memory_error_penalty < 1:
                penalty = "%d%% penalty applied" % ((1 - self.valgrind_memory_error_penalty) * 100)
            output += "Valgrind memory error detected! (%s)\n" % (penalty)

        if self.disallowed_components:
            penalty = "%d%% penalty applied" % ((1 - self.disallowed_components_penalty) * 100)
            output += "The following disallowed components were detected: %s (%s)\n"% (self.disallowed_components, penalty)

        if self.is_segfault:
            output += "Segfault detected!\n"

        if self.diff:
            output += "The actual output did not match the expected output!\n"
            output += "\n###### DIFF ######\n"
            if self.diff_truncated:
                output += "###### The diff output was truncated because it's larger than 1MB! ######\n"
                output += "###### This is most likely due to an infinite loop! ######\n"
            output += self.diff
            if self.actual_truncated:
                output += "###### The actual output was truncated because it's larger than 1MB! ######\n"
                output += "###### This is most likely due to an infinite loop! ######\n"
            output += "\n###### ACTUAL ######\n"
            output += self.actual

        return {
            "name": self.name,
            "score": self.score,
            "max_score": self.max_score,
            "output": output,
            "visibility": self.visibility
        }

class Grader():
    """
    Grade code and circuits.
    """
    def __init__(self, test_suite, settings_file, make_expected=False):
        self.test_suite = test_suite
        self.make_expected = make_expected

        with open(settings_file, "r") as sfile:
            setting = json.load(sfile)

        self.test_dir = setting["test_dir"]
        
        self.timeout_default = setting.get("timeout",TEST_CASE_TIMEOUT_DEFAULT)

        self.mode = setting["mode"]
        assert self.mode in VALID_TEST_MODES, "Invalid test mode."
        
        if self.mode == "logisim":
            # find java
            self.java = find_java()

        try:
            self.force_suite_filename = setting["force_suite_filename"]
        except KeyError:
            self.force_suite_filename = ""

        try:
            self.disallowed_components = setting["disallowed_components"]
        except KeyError:
            self.disallowed_components = None

        self.test_suite_names = setting["test_suite_names"]
        self.non_zero_exit_status_penalty = setting.get("non_zero_exit_status_penalty",1.0)
        self.memory_penalty = setting.get("memory_penalty",1.0)
        self.modulus_penalty = setting.get("modulus_penalty",None)
        self.test_suites = setting["test_suites"]
        
        self.will_penalize = {}
        for test_suite_name in self.test_suite_names:
            self.will_penalize[test_suite_name] = 1.0  # for applying suite-level penalties on a per-test basis (kinda kludgy)

    def run(self):
        """
        Run the autograder.
        """
        self.clean()

        test_outputs = []
        total_score = 0

        if self.test_suite == "ALL":
            for test_suite_name in self.test_suite_names:
                test_outputs, total_score = self.run_test_suite(test_suite_name, test_outputs, total_score)
        elif self.test_suite == "CLEAN":
            self.clean()
        elif self.test_suite in self.test_suite_names:
            test_outputs, total_score = self.run_test_suite(self.test_suite, test_outputs, total_score)
        else:
            raise Exception("Invalid test provided: %s" (self.test_suite))

        return test_outputs, total_score

    def run_test_suite(self, test_suite_name, test_outputs, total_score):
        """
        Run a test suite.
        """
        print("Running tests for %s..." % (test_suite_name))
        
        if self.modulus_penalty:
            # check for mod use for this suite -- actual penalty to be applied at the per-test level
            if modulus_used(test_suite_name):
                print(TextColors.RED + "*!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!*" + TextColors.END)
                print(TextColors.RED + "* %s: MODULUS USE DETECTED IN SOURCE CODE - PENALTY APPLIED!" % test_suite_name + TextColors.END)
                print(TextColors.RED + "* All test scores will be multiplied by %.2f!" % self.modulus_penalty + TextColors.END)
                print(TextColors.RED + "*!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!*" + TextColors.END)
                self.will_penalize[test_suite_name] *= self.modulus_penalty

        for test_num, test_case in enumerate(self.test_suites[test_suite_name]):
            test_output, points = self.run_test_case(test_suite_name, test_case, test_num)
            test_outputs.append(test_output)
            total_score += points

        print("Done running tests for %s.\n" % (test_suite_name))

        return test_outputs, total_score

    def run_test_case(self, test_suite_name, test_case, test_num):
        """
        Run a specific test case.
        """
        description = test_case["desc"]
        args = test_case["args"]
        is_valgrind = test_case.get("valgrind",False) # default False
        diff_type = test_case.get("diff","normal") # default "normal"
        filter_type = test_case.get("filter","none") # default "none"
        timeout = test_case.get("timeout",self.timeout_default) # defaults to top-level timeout (which itself defaults to TEST_CASE_TIMEOUT_DEFAULT if omitted)

        max_points = 0
        display_points = False
        if "points" in test_case:
            max_points = test_case["points"]
            display_points = True

        visibility = "visible"
        if "visibility" in test_case:
            visibility = test_case["visibility"]

        is_pass, exit_status_non_zero, memory_error, diff, actual, is_segfault = self.execute_test(test_suite_name,
                                                                                                   test_num, args,
                                                                                                   is_valgrind,
                                                                                                   diff_type, filter_type, timeout=timeout)

        points = max_points
        if exit_status_non_zero:
            points = points * self.non_zero_exit_status_penalty
        if memory_error:
            points = points * self.memory_penalty
            
        points *= self.will_penalize[test_suite_name] # apply suite-level penalties to this test (e.g. modulus penalty); factor defaults to 1.0 if no penalty

        disallowed_components = None
        disallowed_components_penalty = 1.0

        if self.mode == "logisim" and self.disallowed_components:
            penalties = self.disallowed_components[test_suite_name]
            disallowed_components, disallowed_components_penalty = self.logisim_check_allowed(test_suite_name + ".circ",
                                                                                              penalties)
            points = points * disallowed_components_penalty

        test_output = TestOutput("%s test %d: %s" % (test_suite_name, test_num, description),
                                 points if is_pass else 0,
                                 max_points,
                                 diff,
                                 actual,
                                 exit_status_non_zero,
                                 self.non_zero_exit_status_penalty,
                                 memory_error,
                                 self.memory_penalty,
                                 is_valgrind,
                                 is_segfault,
                                 visibility,
                                 disallowed_components,
                                 disallowed_components_penalty)

        def print_result(test_id, description, status, errors, score=None):
            if score:
                print("%-10s %-50s %-20s %-15s %-45s" % (test_id, description, status, score, errors))
            else:
                print("%-10s %-50s %-20s %-45s" % (test_id, description, status, errors))

        status = TextColors.RED + "Failed" + TextColors.END
        if is_pass:
            status = TextColors.GREEN + "Pass" + TextColors.END

        score = None
        if display_points:
            score = "%0.2f/%0.2f" % ((points if is_pass else 0), max_points)

        errors = ""
        if exit_status_non_zero:
            errors += TextColors.RED + "exit_status_non_zero" + TextColors.END + "  "
        if memory_error:
            errors += TextColors.RED + "valgrind_memory_error" + TextColors.END

        print_result("Test %d " % test_num,
                     "(%s):" % description,
                     status,
                     errors,
                     score)

        return test_output, points if is_pass else 0
        
    def execute_test(self, test_suite_name, test_num, args, is_valgrind, diff_type, filter_type, timeout=None):
        """
        Execute a test, get output and calculate score.
        """
        executable_file_name = None
        if self.force_suite_filename:
            executable_file_name = self.force_suite_filename
        elif self.mode == "exe":
            executable_file_name = test_suite_name
        elif self.mode == "spim":
            executable_file_name = test_suite_name + ".s"
        elif self.mode == "logisim":
            executable_file_name = test_suite_name + ".circ"

        expected_output_filename = os.path.join(self.test_dir, "%s_expected_%d.txt" % (test_suite_name, test_num))
        actual_output_filename = os.path.join(self.test_dir, "%s_actual_%d.txt" % (test_suite_name, test_num))
        diff_filename = os.path.join(self.test_dir, "%s_diff_%d.txt" % (test_suite_name, test_num))

        input_file = None
        if self.mode == "exe":
            command = "./%s" % executable_file_name
            arguments = args
        elif self.mode == "spim":
            command = "spim"
            arguments = ["-f", executable_file_name]
            input_file = open(args[0], "r")
        elif self.mode == "logisim":
            command = self.java
            arguments = ["-jar", "logisim_cli.jar", "-f", executable_file_name] + args

        if self.make_expected: # special mode to generate expected outputs - kinda hacky in how it short circuits things
            print("Generating '%s'..." % expected_output_filename)
            output_file = open(expected_output_filename, "w+")
            exit_status = self.run_process(command, arguments, output_file, input_file)
            if self.mode == "spim":
                try:
                    spim_clean(expected_output_filename)
                except Exception as e:
                    print("Exception when running spim_clean: %s" % e)            
            if filter_type == "logisim_strip_blank_probes":
                logisim_strip_blank_probes(expected_output_filename)
            is_pass, exit_status_non_zero, memory_error, diff, actual, is_segfault = (True, False, False, "", "", False)
            return is_pass, exit_status_non_zero, memory_error, diff, actual, is_segfault
            
        output_file = open(actual_output_filename, "w+")
        exit_status = self.run_process(command, arguments, output_file, input_file, timeout=timeout)
        exit_status_non_zero = exit_status != 0
        is_segfault = exit_status == -11

        if self.mode == "spim":
            try:
                spim_clean(actual_output_filename)
            except Exception as e:
                print("Exception when running spim_clean: %s" % e)
        if filter_type == "logisim_strip_blank_probes":
            logisim_strip_blank_probes(actual_output_filename)

        if diff_type == "normal":
            is_pass = self.normal_diff(expected_output_filename, actual_output_filename, diff_filename)
        elif diff_type == "float":
            is_pass = self.float_diff(expected_output_filename, actual_output_filename, diff_filename)

        memory_error = False
        if is_valgrind:
            command = "valgrind"
            arguments = [
                "-q",
                "--error-exitcode=88",
                "--show-reachable=yes",
                "--leak-check=full",
                "./%s" % executable_file_name,
            ] + args
            exit_status = self.run_process(command, arguments, timeout=timeout)
            if exit_status == 88:
                memory_error = True

        with open(diff_filename, "r") as diff_file:
            try:
                diff = diff_file.read()
            except Exception as e:
                diff = "There was a problem reading the diff file. This is likely due to a problem with your submission causing a non-ASCII character to be written to the diff file."
                print("Exception when running diff: %s" % (e))

        with open(actual_output_filename, "r") as actual_file:
            try:
                actual = actual_file.read()
            except Exception as e:
                actual = "There was a problem reading the actual file. This is likely due to a problem with your submission causing a non-ASCII character to be written to the actual file."
                print("Exception when running actual: %s" % (e))

        return is_pass, exit_status_non_zero, memory_error, diff, actual, is_segfault

    def normal_diff(self, expected_output_filename, actual_output_filename, diff_filename):
        """
        Simple diff.
        """
        command = "diff"
        arguments = ["-bwB", expected_output_filename, actual_output_filename]
        output_file = open(diff_filename, "w+")
        exit_status = self.run_process(command, arguments, output_file)
        return exit_status == 0

    def float_diff(self, expected_output_filename, actual_output_filename, diff_filename, frac_delta=0.001):
        """
        Float diff with tolerance.
        """
        expected_output = open(expected_output_filename, "r")
        actual_output = open(actual_output_filename, "r")
        diff = open(diff_filename, "w")
        is_pass = True

        def line_match(line1, line2):
            if line1 == line2:
                return True
            match1 = re.match(r"(\w+)\s+([.\d]+)$", line1)
            if not match1:
                return False
            match2 = re.match(r"(\w+)\s+([.\d]+)$", line2)
            if not match2:
                return False
            key1 = match1.group(1)
            value1 = float(match1.group(2))
            key2 = match2.group(1)
            value2 = float(match2.group(2))
            if key1 != key2:
                return False
            if frac_delta is not None and abs(frac_difference(value1, value2)) > frac_delta:
                return False
            return True

        # Fraction difference (i.e. percent difference but not x100) between two numbers
        # Special cases: if a=b=0, returns 0.0, if b=0 & a!=b, returns 1.0
        def frac_difference(num1, num2):
            if num2 == 0:
                if num1 == 0:
                    return 0.0
                else:
                    return 1.0
            return num1/num2 - 1.0

        for line1, line2 in zip_longest(expected_output, actual_output, fillvalue=""):
            line1 = line1.rstrip()
            line2 = line2.rstrip()
            if not line_match(line1, line2):
                diff.write("< %s\n> %s\n" % (line1, line2))
                is_pass = False

        expected_output.close()
        actual_output.close()
        diff.close()

        return is_pass

    def run_process(self, command, arguments, output_file=None, input_file=None, timeout=TEST_CASE_TIMEOUT_DEFAULT):
        """
        Execute a shell command and return exit code.
        command: string
        arguments: list of strings
        output_file: file to write output
        """
        try:
            if output_file is not None:
                return my_check_call([command] + arguments,
                                             stdout=output_file,
                                             stderr=output_file,
                                             stdin=input_file,
                                             timeout=timeout,
                                             shell=False)
            return my_check_call([command] + arguments,
                                         stdout=DEVNULL,
                                         stderr=DEVNULL,
                                         stdin=input_file,
                                         timeout=timeout,
                                         shell=False)
        except subprocess.CalledProcessError as exception:
            return exception.returncode
        except Exception as exception:
            print("run_process: %s" % exception)
            return -1



    def logisim_check_allowed(self, file_name, penalty_info):
        """
        Check if disallowed component is used in Logisim circuit.
        """
        if not os.path.exists(file_name):
            return [], 1.0

        tree = ET.parse(file_name)
        root = tree.getroot()

        components_found = []
        min_penalty = 1.0

        for child in root:
            if child.tag == "circuit":
                for subchild in child:
                    for penalties in penalty_info:
                        if subchild.tag == "comp" and subchild.attrib["name"] in penalties["components"]:
                            components_found.append(subchild.attrib["name"])
                            min_penalty = min(min_penalty, penalties["penalty"])

        return components_found, min_penalty

    def clean(self):
        """
        Remove the output of running tests.
        """
        os.system("rm -f " +
                  os.path.join(self.test_dir, "*_actual_*.txt*") + " " +
                  os.path.join(self.test_dir, "*_diff_*.txt*"))
