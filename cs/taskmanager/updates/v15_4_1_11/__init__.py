import json

from cdb import sqlapi


class UpdateFileListUserSettings(object):
    id1 = "cs.taskmanager"
    id2 = "settings"

    def run(self):
        file_list_setting_key = "showFileList"
        file_list_setting_value = True
        table_name = "cdb_usr_setting_long_txt"
        condition = "setting_id='{}' AND setting_id2='{}'".format(self.id1, self.id2)

        existing_usr_settings = sqlapi.RecordSet2(table_name, condition)
        for usr_setting in existing_usr_settings:
            # parse the settings text
            parsed_settings = json.loads(usr_setting.text)

            # if no settings exist add them
            if file_list_setting_key not in parsed_settings:
                parsed_settings[file_list_setting_key] = file_list_setting_value

                # update the record
                new_settings = json.dumps(parsed_settings)
                usr_setting.update(text=new_settings)


pre = []
post = [UpdateFileListUserSettings]

if __name__ == "__main__":
    UpdateFileListUserSettings().run()
