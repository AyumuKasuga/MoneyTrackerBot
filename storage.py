from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials


class MoneyTrackerStorage(object):

    def __init__(self, keyfile, spreadsheet_name):
        self.keyfile = keyfile
        self.spreadsheet_name = spreadsheet_name
        self.spreadsheet, self.wks = None, None
        self.total_cell_coordinates = (3, 7)
        self.monthly_limit_cell_coordinates = (4, 7)

    def reselect_sheet(self):
        current_name = datetime.now().strftime('%B %Y')
        try:
            self.wks = self.spreadsheet.worksheet(current_name)
        except gspread.WorksheetNotFound:
            wks = self.spreadsheet.add_worksheet(current_name, cols=20, rows=1000)
            wks.update_cell(1, 1, 'datetime')
            wks.update_cell(1, 2, 'sum')
            wks.update_cell(1, 3, 'category')
            wks.update_cell(1, 4, 'person')
            wks.update_cell(1, 5, 'description')
            wks.update_cell(*self.total_cell_coordinates, '=sum(B2:B1000)')
            self.reselect_sheet()

    def reauthorize(self):
        scope = ['https://spreadsheets.google.com/feeds']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(self.keyfile, scope)
        gc = gspread.authorize(credentials)
        self.spreadsheet = gc.open(self.spreadsheet_name)

    def get_next_empty_row(self):
        for i, x in enumerate(self.wks.col_values(1)):
            if x == '':
                return i + 1

    def get_total_and_limit(self):
        self.reauthorize()
        self.reselect_sheet()
        cell_list = self.wks.range(
            *self.total_cell_coordinates,
            *self.monthly_limit_cell_coordinates
        )
        return [x.value for x in cell_list]

    def set_limit(self, limit):
        self.reauthorize()
        self.reselect_sheet()
        self.wks.update_cell(*self.monthly_limit_cell_coordinates, str(limit))

    def add_entry(self, sum, category, person, description=''):
        self.reauthorize()
        self.reselect_sheet()
        row = self.get_next_empty_row()
        cell_list = self.wks.range(row, 1, row, 5)
        data_list = (str(datetime.now()), sum, category, person, description)
        for cell, data in zip(cell_list, data_list):
            cell.value = data
        self.wks.update_cells(cell_list)
        return self.get_total_and_limit()

    def export_worksheet(self):
        self.reauthorize()
        self.reselect_sheet()
        return self.wks.export('pdf')
