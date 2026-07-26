/**
 * Simple Python syntax highlighter for the script editor.
 * Provides basic keyword, string, and comment highlighting.
 */
(function() {
  'use strict';
  
  var PYTHON_KEYWORDS = [
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield'
  ];
  
  var PYTHON_BUILTINS = [
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
    'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr',
    'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter',
    'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr',
    'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance', 'issubclass',
    'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min',
    'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property',
    'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
    'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type',
    'vars', 'zip'
  ];
  
  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;');
  }
  
  function highlightPython(code) {
    var lines = code.split('\n');
    var result = [];
    
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var highlighted = '';
      var j = 0;
      
      while (j < line.length) {
        // Comments
        if (line[j] === '#') {
          highlighted += '<span style="color:#888;font-style:italic;">' + escapeHtml(line.substring(j)) + '</span>';
          break;
        }
        
        // Strings (single or double quoted, including triple quotes)
        if (line[j] === '"' || line[j] === "'") {
          var quote = line[j];
          var k = j + 1;
          while (k < line.length && line[k] !== quote) {
            if (line[k] === '\\') k++; // Skip escaped chars
            k++;
          }
          k++; // Include closing quote
          highlighted += '<span style="color:#080;">' + escapeHtml(line.substring(j, k)) + '</span>';
          j = k;
          continue;
        }
        
        // Keywords
        var wordStart = j;
        while (j < line.length && /[a-zA-Z0-9_]/.test(line[j])) j++;
        var word = line.substring(wordStart, j);
        
        if (PYTHON_KEYWORDS.indexOf(word) !== -1) {
          highlighted += '<span style="color:#00f;font-weight:bold;">' + escapeHtml(word) + '</span>';
        } else if (PYTHON_BUILTINS.indexOf(word) !== -1) {
          highlighted += '<span style="color:#008;">' + escapeHtml(word) + '</span>';
        } else {
          highlighted += escapeHtml(word);
        }
      }
      
      result.push(highlighted);
    }
    
    return result.join('\n');
  }
  
  // Auto-highlight on input
  function initHighlighter(textareaId) {
    var textarea = document.getElementById(textareaId);
    if (!textarea) return;
    
    var preview = document.createElement('div');
    preview.id = textareaId + '-preview';
    preview.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;padding:8px;overflow:auto;font-family:monospace;font-size:13px;line-height:1.5;pointer-events:none;white-space:pre-wrap;word-wrap:break-word;color:transparent;';
    textarea.style.position = 'relative';
    textarea.parentNode.style.position = 'relative';
    textarea.parentNode.insertBefore(preview, textarea);
    
    function update() {
      preview.innerHTML = highlightPython(textarea.value) + '\n';
    }
    
    textarea.addEventListener('input', update);
    textarea.addEventListener('scroll', function() {
      preview.scrollTop = textarea.scrollTop;
      preview.scrollLeft = textarea.scrollLeft;
    });
    
    update();
  }
  
  // Initialize all script textareas
  document.addEventListener('DOMContentLoaded', function() {
    initHighlighter('source_code');
  });
  
  // Expose for manual use
  window.highlightPython = highlightPython;
  window.initHighlighter = initHighlighter;
})();
