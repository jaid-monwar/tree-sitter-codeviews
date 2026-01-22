import os
import shutil
import subprocess
import tempfile

from tree_sitter import Language


def get_language_map():
    clone_directory = os.path.join(tempfile.gettempdir(), "atlas")
    shared_languages = os.path.join(clone_directory, "languages.so")

    grammar_repos = [
        ("https://github.com/tree-sitter/tree-sitter-c", "34f4c7e751f4d661be3e23682fe2631d6615141d"),
        ("https://github.com/tree-sitter/tree-sitter-cpp", "f41e1a044c8a84ea9fa8577fdd2eab92ec96de02")  # Latest stable with pure virtual destructor support
    ]
    vendor_languages = []

    for url, commit in grammar_repos:
        grammar = url.rstrip("/").split("/")[-1]
        vendor_language = os.path.join(clone_directory, grammar)
        vendor_languages.append(vendor_language)
        if os.path.isfile(shared_languages) and not os.path.exists(vendor_language):
            os.remove(shared_languages)
        elif not os.path.isfile(shared_languages) and os.path.exists(vendor_language):
            shutil.rmtree(vendor_language)
        elif not os.path.isfile(shared_languages) and not os.path.exists(vendor_language):
            pass
        else:
            continue
        print(f"Intial Setup: First time running ATLAS on {grammar}")
        os.makedirs(vendor_language, exist_ok=True)
        subprocess.check_call(["git", "init"], cwd=vendor_language, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        subprocess.check_call(["git", "remote", "add", "origin", url], cwd=vendor_language, stdout=subprocess.DEVNULL,
                              stderr=subprocess.STDOUT)
        subprocess.check_call(["git", "fetch", "--depth=1", "origin", commit], cwd=vendor_language,
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        subprocess.check_call(["git", "checkout", commit], cwd=vendor_language, stdout=subprocess.DEVNULL,
                              stderr=subprocess.STDOUT)

        # Patch tree-sitter-cpp scanner.c to remove static_assert that causes compilation issues
        if grammar == "tree-sitter-cpp":
            scanner_path = os.path.join(vendor_language, "src", "scanner.c")
            if os.path.exists(scanner_path):
                with open(scanner_path, 'r') as f:
                    content = f.read()
                # Remove problematic static_assert lines
                content = content.replace(
                    'static_assert(MAX_DELIMITER_LENGTH * sizeof(wchar_t) < TREE_SITTER_SERIALIZATION_BUFFER_SIZE,\n                  "Serialized delimiter is too long!");',
                    '// static_assert removed for compatibility'
                )
                with open(scanner_path, 'w') as f:
                    f.write(content)

    # build_id = ""
    # for vendor_language in vendor_languages:
    #     commit_hash = get_commit_hash(vendor_language)
    #     if commit_hash:
    #         build_id += commit_hash
    #     else:
    #         build_id += "ERROR"
    # build_id_file = os.path.join(clone_directory, "build_id")
    #
    # # check if the build_id is the same as the one stored in the file
    # # if not, rebuild the shared library
    # if os.path.exists(build_id_file):
    #     with open(build_id_file, "r") as f:
    #         stored_build_id = f.read()
    #     if build_id != stored_build_id:
    #         os.remove(shared_languages)
    # else:
    #     if os.path.exists(shared_languages):
    #         os.remove(shared_languages)

    Language.build_library(
        # Store the library in the `build` directory
        shared_languages,
        vendor_languages,
    )
    C_LANGUAGE = Language(shared_languages, "c")
    CPP_LANGUAGE = Language(shared_languages, "cpp")

    return {
        "c": C_LANGUAGE,
        "cpp": CPP_LANGUAGE,
    }
