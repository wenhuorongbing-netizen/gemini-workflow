import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Make sure the save button is disabled when cron is invalid
old_save_btn = """            <button
              onClick={handleSave}
              disabled={!selectedWorkspace || isSaving}
              className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
            >"""

new_save_btn = r"""            <button
              onClick={handleSave}
              disabled={
                !selectedWorkspace ||
                isSaving ||
                nodes.some(n =>
                  n.type === 'trigger' &&
                  n.data?.triggerType === 'cron' &&
                  n.data?.cron &&
                  !/^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-3])|\*\/([0-9]|1[0-9]|2[0-3])) (\*|([1-9]|1[0-9]|2[0-9]|3[0-1])|\*\/([1-9]|1[0-9]|2[0-9]|3[0-1])) (\*|([1-9]|1[0-2])|\*\/([1-9]|1[0-2])) (\*|([0-6])|\*\/([0-6]))$/.test(n.data.cron as string)
                )
              }
              className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >"""

if old_save_btn in content:
    content = content.replace(old_save_btn, new_save_btn)
else:
    print("Could not find the old save button block.")

with open('app/page.tsx', 'w') as f:
    f.write(content)
