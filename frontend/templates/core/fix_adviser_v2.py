import os
import re

file_path = r'c:\Users\longa\Documents\websys_copy\django\core\templates\core\adviser.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fuzzy match for the start and end of the loop
start_pattern = r'data\.curriculum\.forEach\(subj => \{'
end_pattern = r'body\.insertAdjacentHTML\(\'beforeend\', row\);\s*\}\);'

# New logic
new_block = """// Group by Year and Semester
          const groups = {};
          data.curriculum.forEach(subj => {
            const key = `Year ${subj.year_level}, Semester ${subj.semester}`;
            if (!groups[key]) groups[key] = [];
            groups[key].push(subj);
          });
          
          Object.entries(groups).forEach(([groupName, subjects], idx) => {
            const sectionId = `curr-section-${idx}`;
            accordion.insertAdjacentHTML('beforeend', `
              <div class="curr-section border-b last:border-b-0" data-year="${subjects[0].year_level}">
                <button onclick="document.getElementById('${sectionId}').classList.toggle('hidden')" 
                        class="w-full px-4 py-3 bg-white hover:bg-gray-50 flex items-center justify-between transition-colors sticky top-0 z-10 border-b">
                  <span class="font-bold text-gray-700 text-xs uppercase tracking-wider">${groupName}</span>
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-gray-400 transition-transform"><path d="m6 9 6 6 6-6"/></svg>
                </button>
                <div id="${sectionId}" class="bg-white">
                  <table class="w-full text-sm">
                    <tbody class="divide-y divide-gray-50">
                      ${subjects.map(subj => {
                        const statusClass = {
                           'passed': 'bg-green-100 text-green-700 border-green-200',
                           'failed': 'bg-red-100 text-red-700 border-red-200',
                           'in_progress': 'bg-blue-100 text-blue-700 border-blue-200',
                           'not_taken': 'bg-gray-100 text-gray-500 border-gray-200'
                        }[subj.status] || 'bg-gray-100';
                        
                        return `
                          <tr class="curr-row hover:bg-blue-50/30 transition-colors" data-year="${subj.year_level}">
                            <td class="p-3 w-10">
                              <input type="checkbox" class="subject-checkbox size-4 rounded border-gray-300 text-light-blue focus:ring-light-blue" 
                                     value="${subj.id}" data-code="${subj.code}" ${subj.status === 'passed' ? 'disabled' : ''} onchange="toggleSubjectSelection(this)">
                            </td>
                            <td class="p-3 font-mono text-[10px] font-bold text-navy w-24">${subj.code}</td>
                            <td class="p-3">
                              <p class="font-medium text-gray-900 leading-tight">${subj.title}</p>
                              <p class="text-[9px] text-gray-400 mt-0.5">${subj.units} Units · Year ${subj.year_level}, Sem ${subj.semester}</p>
                            </td>
                            <td class="p-3 w-24 text-center">
                              <span class="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-bold border ${statusClass} capitalize whitespace-nowrap">
                                ${subj.status.replace('_', ' ')}
                              </span>
                            </td>
                            <td class="p-3 w-32">
                              <select onchange="updateSubjectStatus(${selectedStudentId}, ${subj.id}, this.value)" class="text-[10px] border rounded px-1 py-1 outline-none w-full bg-white font-medium text-gray-600">
                                <option value="not_taken" ${subj.status === 'not_taken' ? 'selected' : ''}>Not Taken</option>
                                <option value="passed" ${subj.status === 'passed' ? 'selected' : ''}>Passed</option>
                                <option value="failed" ${subj.status === 'failed' ? 'selected' : ''}>Failed</option>
                                <option value="in_progress" ${subj.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                              </select>
                            </td>
                          </tr>
                        `;
                      }).join('')}
                    </tbody>
                  </table>
                </div>
              </div>
            `);
          });"""

# Use regex to find and replace the entire function body segment
full_pattern = start_pattern + r'.*?' + end_pattern
new_content, count = re.subn(full_pattern, new_block, content, flags=re.DOTALL)

if count > 0:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Success! Replaced {count} instance(s).")
else:
    print("Failed to find the pattern even with fuzzy regex.")
