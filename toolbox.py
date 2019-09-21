import logging
import json
import bson
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from os import system
from os.path import abspath
from collections import OrderedDict


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
logging.info('Program started')


# https://stackoverflow.com/a/16375233
class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget

    def redraw(self, *args):
        '''redraw line numbers'''
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True :
            dline= self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2,y,anchor="nw", text=linenum)
            i = self.textwidget.index("%s+1line" % i)
class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)

        # create a proxy for the underlying widget
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        # let the actual widget perform the requested action
        cmd = (self._orig,) + args
        try:
            result = self.tk.call(cmd)
        except Exception:
            return None

        # generate an event if something was added or deleted,
        # or the cursor position changed
        if (args[0] in ("insert", "replace", "delete") or
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] == ("xview", "moveto") or
            args[0:2] == ("xview", "scroll") or
            args[0:2] == ("yview", "moveto") or
            args[0:2] == ("yview", "scroll")
        ):
            self.event_generate("<<Change>>", when="tail")

        # return what the actual widget returned
        return result
class TextExtra(tk.Frame):
    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)
        self.text = CustomText(self, wrap='none', font=('verdana', '7'))
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.hsb = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        self.text.tag_configure("bigfont", font=("Helvetica", "24", "bold"))
        self.linenumbers = TextLineNumbers(self, width=20)
        self.linenumbers.attach(self.text)

        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side='bottom', fill='x')
        self.linenumbers.pack(side="left", fill="y")
        self.text.pack(side="right", fill="both", expand=True)

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

    def _on_change(self, event):
        self.linenumbers.redraw()

    def delete(self, *args, **kwargs):
        self.text.delete(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.text.get(*args, **kwargs)

    def see(self, *args, **kwargs):
        self.text.see(*args, **kwargs)
        self._on_change(event="<<Change>>")

    def insert(self, *args, **kwargs):
        self.text.insert(*args, **kwargs)

    def configure(self, *args, **kwargs):
        self.text.configure(*args, **kwargs)

    def cget(self, *args, **kwargs):
        return self.text.cget(*args, **kwargs)


class JsonFile:
    def __init__(self, path):
        self.file_path = path
        self.json_original_text = None
        self.json_text = None
        self.host = None
        self.hostname = None
        self.scheme = None
        self.json_object = None
        self.tests_available = list()
        self.status = ''

        self._tests_all = [
            'manga_list_complete', 'manga_search_complete', 'manga_complete',
            'anime_list_complete', 'anime_search_complete', 'anime_complete', 'episodes_complete'
        ]

        self._load_file(path)
        self._load_json()
        self._parse_tests()

        if self.status != 'invalid':
            self._parse_host()
            self._convert_links()
            self._parse_search_link()

    def get_json_original_text(self):
        return self.json_original_text

    def _parse_search_link(self):
        tmp_json_object = json.loads(self.json_text, object_pairs_hook=OrderedDict)
        try:
            self.search_link = tmp_json_object['anime_search_complete']['search_link']
            logging.debug('search_link ' + self.search_link)
        except KeyError:
            try:
                self.search_link = tmp_json_object['manga_search_complete']['search_link']
                logging.debug('search_link ' + self.search_link)
            except KeyError:
                logging.warning('search_link not found')

    def _clean_all(self):
        self.json_text = None
        self.host = None
        self.hostname = None
        self.scheme = None
        self.json_object = None
        self.tests_available = list()

    def _parse_host(self):
        self.host = self.json_object['host'].strip('/')
        self.scheme = self.host.split('//')[0]
        self.hostname = self.host.split('//')[1]

    def _parse_tests(self):
        if self.status != 'invalid':
            for item in self._tests_all:
                if item in self.json_object.keys():
                    self.tests_available.append(item)

            logging.debug('Available tests: ' + str(self.tests_available))
        else:
            tmp = self._tests_all.copy()
            tmp.remove('anime_search_complete')
            tmp.remove('manga_search_complete')
            self.tests_available = tmp
            logging.warning('Tests parsing skipped, using tests_all: ' + str(self.tests_available))

    def _load_file(self, path):
        with open(path, 'r', encoding='utf8') as f:
            self.json_text = f.read()
            self.json_original_text = self.json_text
            logging.info('Loading file ' + path)

    def _load_json(self):
        try:
            self.json_object = json.loads(self.json_text, object_pairs_hook=OrderedDict)
            self.status = 'valid'
        except json.JSONDecodeError:
            logging.warning("Got decode error, trying to fix json...")
            self.status = 'mangled'
            self._clean_json_string()
            try:
                self.json_object = json.loads(self.json_text, object_pairs_hook=OrderedDict)
                logging.warning("Json fixed and loaded")
            except json.JSONDecodeError:
                logging.error("Invalid JSON")
                self.status = 'invalid'

    def _convert_links(self):
        self.json_text = self.json_text.replace('$scheme$', self.scheme)
        self.json_text = self.json_text.replace('$hostname$', self.hostname)
        self.json_text = self.json_text.replace(r'%%host%%', self.host)

    def _clean_json_string(self):
        """
        Clears json from trailing commas

        https://stackoverflow.com/a/23705538
        It will mangle inputs like '{"foo": ",}"}'
        """
        self.json_text = re.sub(",[ \t\r\n]+}", "}", self.json_text)
        self.json_text = re.sub(",[ \t\r\n]+\]", "]", self.json_text)


class App:
    def __init__(self):
        self.root = tk.Tk()

        self.temp_file_path = None
        self.json_file = None
        self.test_query = {
            "manga_list_complete":   'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}]',
            "manga_search_complete": 'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}] "{search_link}" "{query}"',
            "manga_complete":        'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}] "{query}"',
            "anime_search_complete": 'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}] "{search_link}" "{query}"',
            "anime_list_complete":   'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}]',
            "anime_complete":        'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}] "{query}"',
            "episodes_complete":     'java -jar NigmaX-2.1.jar --console test "{parser_path}" [{test_method}] "{query}" "{query}" "{query}"',
        }

        self.tests_available = ['Select parser. Tests will appear here']
        self.create_main_window()
        self.root.mainloop()

    def create_main_window(self):
        self.root.geometry("400x600")
        self.root.resizable(False, False)
        self.root.title("RadianceX Toolbox")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(padx=2, pady=2, fill='both', expand='true')

        self.create_tab1()
        self.create_tab2()
        self.create_tab3()

    def create_tab1(self):
        self.tab1 = ttk.Frame(self.notebook)

        self.parser_path = tk.StringVar()
        self.radio_button_value = tk.IntVar()

        # tab1 > header > entry
        self.header = tk.Frame(self.tab1)
        self.header.pack(fill='x', pady=5)
        self.entry_path = tk.Entry(self.header, highlightbackground="#bebebe", highlightthickness=1,
                                   textvariable=self.parser_path)
        self.entry_path.pack(side='left', fill='x', padx=5, expand=True, ipady=1)

        # tab1 > header > button
        self.btn_select = ttk.Button(self.header, text="select", command=self.__btn_select_click)
        self.btn_select.pack(side='right', padx=5)

        # tab1 > label_json_status
        self.label_json_status = tk.Label(self.tab1, text='json status')
        self.label_json_status.pack(anchor='w', padx=5)

        # tab1 > tests_frame
        self.tests_frame = tk.LabelFrame(self.tab1, text="tests", padx=5, pady=5)
        self.tests_frame.pack(padx=5, pady=5, fill='both')
        self.update_tests_available_frame()

        # tab1 > entry
        self.entry_query = tk.Entry(self.tab1, highlightbackground="#bebebe", highlightthickness=1)
        self.entry_query.pack(padx=5, pady=5, fill='x')

        # tab1 > button
        self.btn_run = ttk.Button(self.tab1, text='RUN', command=self.__btn_run_click)
        self.btn_run.pack(padx=5, pady=5, fill='x')

        self.notebook.add(self.tab1, text="Tests")

    def create_tab2(self):
        self.tab2 = ttk.Frame(self.notebook)
        self.label_validate_result_text = tk.StringVar()
        # self.label_validate_result_text.set('test output')

        # tab2 > header
        header = tk.Frame(self.tab2)
        header.pack(fill='x')

        # tab2 > header > text_box
        self.text_box = TextExtra(header, highlightbackground="#bebebe")
        font = tkfont.Font(font=self.text_box.cget('font'))
        tab_width = font.measure(' ' * 4)
        self.text_box.configure(tabs=(tab_width,))
        self.text_box.pack(padx=5, pady=5)

        # tab2 > validate_buttons_frame
        validate_buttons_frame = tk.Frame(self.tab2)
        validate_buttons_frame.pack(padx=5, fill='x')

        # tab2 > validate_buttons_frame > btn_validate
        self.btn_validate = ttk.Button(validate_buttons_frame, text='validate json', command=self.__btn_validate_click)
        self.btn_validate.pack(side='left', padx=5, pady=5)

        # tab2 > validate_buttons_frame > btn_clear
        self.btn_clear = ttk.Button(validate_buttons_frame, text='clear', width=0, command=self.__btn_clear_click)
        self.btn_clear.pack(side='left', padx=5, pady=5)

        # tab2 > labelframe_validate_result
        self.labelframe_validate_result = tk.LabelFrame(self.tab2, text="Results")
        self.labelframe_validate_result.pack(padx=5, fill='x')
        self.label_validate_result = tk.Message(self.labelframe_validate_result, width=380, textvariable=self.label_validate_result_text, foreground='green', font=('consolas', '9'))
        self.label_validate_result.pack(fill='x', padx=5, pady=5)

        self.notebook.add(self.tab2, text="JSON validator")

    def create_tab3(self):
        style = ttk.Style()
        style.configure('W.TButton', font=('calibri', 20))

        self.tab3 = tk.Frame(self.notebook)

        # tab3 > btn_convert_json2bson
        self.btn_convert_json2bson = ttk.Button(self.tab3, text="Convert JSON to BSON", style='W.TButton', command=self.__btn_convert_json2bson_click)
        self.btn_convert_json2bson.pack(fill='x')

        # tab3 > btn_convert_bson2json
        self.btn_convert_bson2json = ttk.Button(self.tab3, text="Convert BSON to JSON", style='W.TButton', command=self.__btn_convert_bson2json_click)
        self.btn_convert_bson2json.pack(fill='x')

        self.notebook.add(self.tab3, text="Converter")

    def __btn_convert_bson2json_click(self):
        logging.debug("__btn_convert_bson2json_click call")
        inp_file_path = filedialog.askopenfilename(initialdir="./", title="Select file", filetypes=(("b files", "*.b"), ("bson files", "*.bson"), ("all files", "*.*")))
        logging.debug("path selected: " + inp_file_path)
        if inp_file_path:
            default_name = inp_file_path.split('/')[-1].split('.')[0]
            with open(inp_file_path, 'rb') as f:
                inp_file = bson.loads(f.read())
                logging.debug("bson file loaded")
            out_file = json.dumps(inp_file, indent=4, ensure_ascii=False)  # unsafe converting
            out_file_path = filedialog.asksaveasfilename(initialdir="./", initialfile=f"{default_name}.json", title="Save as", filetypes=(("json files","*.json"), ("all files", "*.*")))
            if out_file_path:
                with open(out_file_path, 'w', encoding='utf8') as f:
                    f.write(out_file)
                    logging.debug("json successfully written")

    def __btn_convert_json2bson_click(self):
        logging.debug("__btn_convert_json2bson_click call")
        if self.json_file:
            default_name = self.json_file.file_path.split('/')[-1].split('.')[0]
            # set output file path
            out_file_path = filedialog.asksaveasfilename(initialdir="./", initialfile=f"{default_name}.bson", title="Save as", filetypes=(("bson files","*.bson"), ("all files", "*.*")))
            logging.debug("path selected: " + out_file_path)
            if out_file_path:
                try:
                    tmp = json.loads(self.json_file.json_original_text)
                    out_file = bson.dumps(tmp)
                    with open(out_file_path, 'wb') as f:
                        f.write(out_file)
                        logging.debug("bson successfully written")
                except json.decoder.JSONDecodeError as e:
                    messagebox.showerror('Error', e)
                    logging.warning("error due decoding json")
        else:
            # select input file path
            inp_file_path = filedialog.askopenfilename(initialdir="./", title="Select file", filetypes=(("json files", "*.json"), ("all files", "*.*")))
            logging.debug("path selected: " + inp_file_path)
            if inp_file_path:
                default_name = inp_file_path.split('/')[-1].split('.')[0]
                with open(inp_file_path, 'r') as f:
                    inp_file = json.load(f, object_pairs_hook=OrderedDict)  # convert string from file to json object
                    logging.debug("bson file loaded")

                out_file = json.dumps(inp_file, indent=4, ensure_ascii=False)  # unsafe converting
                out_file_path = filedialog.asksaveasfilename(initialdir="./", initialfile=f"{default_name}.bson",
                                                             title="Save as",
                                                             filetypes=(("bson files", "*.bson"), ("all files", "*.*")))
                if out_file_path:
                    with open(out_file_path, 'w', encoding='utf8') as f:
                        f.write(out_file)
                        logging.debug("json successfully written")

    def update_label_json_status(self):
        logging.debug("update_label_json_status call")
        if self.json_file.status == 'valid':
            self.label_json_status.configure(text='valid json', fg='green')
        elif self.json_file.status == 'invalid':
            self.label_json_status.configure(text='invalid json', fg='red')
        elif self.json_file.status == 'mangled':
            self.label_json_status.configure(text='mangled json', fg='orange')

    def __btn_validate_click(self):
        logging.debug("__btn_validate_click call")
        try:
            tmp = json.loads(self.text_box.get('1.0', 'end-1c'))
        except json.JSONDecodeError as err:
            self.label_validate_result.configure(foreground='red')
            self.text_box.see(f'{err.lineno}.{err.colno}')
            logging.warning(err)
            # https://stackoverflow.com/a/35150895
            start, stop = max(0, err.pos - 20), err.pos + 20
            snippet = err.doc[start:stop]
            snippet = snippet.replace('\n', '')
            snippet = snippet.replace('\t', ' ')
            snippet = snippet[0:41]
            snippet = '...' + snippet + '...'
            exact = '-' * (err.pos-start) + '^'
            self.label_validate_result_text.set(f'{err}\n\n{snippet}\n{exact}')
        else:
            self.label_validate_result_text.set('valid json')
            self.label_validate_result.configure(foreground='green')

    def __btn_clear_click(self):
        logging.debug("__btn_clear_click call")
        self.text_box.delete('1.0', tk.END)
        self.text_box.update()

    def use_temp_file(self):
        with open('temp.json', 'w', encoding='utf8') as temp:
            temp.write(self.json_file.json_text)
        self.temp_file_path = abspath(r'.\temp.json')

    def update_tests_available_frame(self):
        logging.debug("update_tests_available_frame call")
        for child in self.tests_frame.winfo_children():
            child.pack_forget()
            child.destroy()

        for i, test_method in enumerate(self.tests_available, 0):
            ttk.Radiobutton(self.tests_frame, text=test_method, variable=self.radio_button_value, value=i).pack(anchor='w')

    def __btn_select_click(self):
        logging.debug("__btn_select_click call")

        path = filedialog.askopenfilename(initialdir="./", title="Select file", filetypes=(("json files","*.json"), ("all files", "*.*")))

        if path:
            self.parser_path.set(path)
            logging.debug(f"SET Path: {path}")
            self.path_selected()

    def path_selected(self):
        self.json_file = JsonFile(self.parser_path.get())
        
        self.tests_available.clear()
        self.tests_available = self.json_file.tests_available
        self.update_tests_available_frame()

        if self.json_file.status == 'invalid':
            self.use_temp_file()
        self.update_label_json_status()

        self.__btn_clear_click()
        self.text_box.insert('1.0', self.json_file.json_original_text)
        self.__btn_validate_click()

    def __btn_run_click(self):
        logging.debug("__btn_run_click call")
        if self.json_file:
            method = self.tests_available[self.radio_button_value.get()]
            test_query = self.test_query.get(method)

            if self.temp_file_path is None:
                parser_path = self.parser_path.get()
            else:
                parser_path = self.temp_file_path

            query = self.entry_query.get()
            test_query = test_query.format(
                parser_path=parser_path,
                test_method=method,
                query=query,
                search_link=self.json_file.search_link)
            logging.debug("RUN " + test_query)

            system("start cmd /k  {command}".format(command=test_query))


def main():
    app = App()


if __name__ == '__main__':
    main()
    logging.info('Program finished')
