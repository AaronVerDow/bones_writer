# Bones Writer

Bones Writer is a command line writer designed to encourage and train writers to flow by removing editing commands. Every keypress is permenant and nothing can be edited, much like journaling with a pen and paper.  

Bones Writer was inspired by ["Writing Down the Bones" by Natalie Goldberg](https://nataliegoldberg.com/books/writing-down-the-bones/).

## Use

This is in a pre-alpha state.

* Run `bones_writer.py`
* Live stats are in the upper right hand corner
* Ctrl-c to exit
* Enter in category and title
* Files are stored in ~/Documents/bones/

## Features

* [x] Autosave files
* [x] Git integration
* [x] No ability to make any edits
* Statistics
  * Tracked stats
    * [x] Total words
    * [x] Time per session
    * [x] Words per minute
    * [x] % mispelled words
    * [ ] % grammar errors per sentance
  * [x] Show stats on session completion
  * [x] Live tracker
  * [x] Save statistics
  * [x] Graph statistics
* [ ] Daily streak tracker
* [x] Automatically blank screen if thinking too long
* [ ] Hostage mode: do not release input controls until word or time goal is met
* [ ] Backspace allowance
* [ ] Resume session
* [x] Change output directory
* Builds
  * [ ] Python package
  * [ ] Nix package
