// File Upload Component for PythonAppFoundry
// Usage: Include this script and add a div with id="file-upload-container" to your form

(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        maxFileSize: 10 * 1024 * 1024, // 10MB default
        allowedTypes: '*', // or specific types like 'image/*', '.pdf,.doc,.docx'
        multiple: false,
        uploadUrl: '/api/upload',
        autoUpload: true,
    };
    
    // File Upload Class
    class FileUploadComponent {
        constructor(containerId, options = {}) {
            this.container = document.getElementById(containerId);
            if (!this.container) {
                console.error(`FileUpload: Container #${containerId} not found`);
                return;
            }
            
            // Merge options
            Object.assign(CONFIG, options);
            
            this.files = [];
            this.uploading = false;
            this.onUploadComplete = options.onUploadComplete || null;
            
            this.init();
        }
        
        init() {
            this.container.innerHTML = `
                <div class="file-upload-wrapper">
                    <div class="file-upload-dropzone" id="dropzone">
                        <div class="file-upload-icon">📁</div>
                        <div class="file-upload-text">
                            <strong>Drag & drop files here</strong>
                            <span>or click to browse</span>
                        </div>
                        <input type="file" id="fileInput" 
                               style="display:none" 
                               ${CONFIG.multiple ? 'multiple' : ''}
                               accept="${CONFIG.allowedTypes !== '*' ? CONFIG.allowedTypes : ''}">
                    </div>
                    <div class="file-upload-list" id="fileList"></div>
                    <div class="file-upload-progress" id="progressBar" style="display:none;">
                        <div class="progress-bar" id="progressFill"></div>
                        <span class="progress-text" id="progressText">Uploading...</span>
                    </div>
                </div>
            `;
            
            this.dropzone = document.getElementById('dropzone');
            this.fileInput = document.getElementById('fileInput');
            this.fileList = document.getElementById('fileList');
            this.progressBar = document.getElementById('progressBar');
            this.progressFill = document.getElementById('progressFill');
            this.progressText = document.getElementById('progressText');
            
            this.bindEvents();
        }
        
        bindEvents() {
            // Click to browse
            this.dropzone.addEventListener('click', () => this.fileInput.click());
            
            // File selection
            this.fileInput.addEventListener('change', (e) => {
                this.handleFiles(e.target.files);
            });
            
            // Drag and drop
            this.dropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                this.dropzone.classList.add('dragover');
            });
            
            this.dropzone.addEventListener('dragleave', () => {
                this.dropzone.classList.remove('dragover');
            });
            
            this.dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                this.dropzone.classList.remove('dragover');
                this.handleFiles(e.dataTransfer.files);
            });
        }
        
        handleFiles(fileList) {
            const files = Array.from(fileList);
            
            // Validate files
            for (const file of files) {
                if (file.size > CONFIG.maxFileSize) {
                    alert(`File "${file.name}" exceeds the maximum size of ${CONFIG.maxFileSize / 1024 / 1024}MB`);
                    continue;
                }
                
                if (CONFIG.allowedTypes !== '*' && !this.isFileTypeAllowed(file)) {
                    alert(`File type "${file.type}" is not allowed`);
                    continue;
                }
                
                this.files.push(file);
            }
            
            this.renderFileList();
            
            // Auto-upload if enabled
            if (CONFIG.autoUpload && this.files.length > 0 && !this.uploading) {
                this.uploadFiles();
            }
        }
        
        isFileTypeAllowed(file) {
            const ext = file.name.split('.').pop().toLowerCase();
            const allowedTypes = CONFIG.allowedTypes.split(',').map(t => t.trim().toLowerCase());
            
            return allowedTypes.some(type => {
                if (type.includes('*')) return true; // Wildcard
                if (type.startsWith('.')) return ext === type.substring(1); // Extension match
                return file.type.startsWith(type); // MIME type match
            });
        }
        
        renderFileList() {
            this.fileList.innerHTML = this.files.map((file, index) => `
                <div class="file-upload-item" data-index="${index}">
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${this.formatSize(file.size)}</span>
                    <button class="file-remove" onclick="window.fileUpload.removeFile(${index})">×</button>
                </div>
            `).join('');
        }
        
        removeFile(index) {
            this.files.splice(index, 1);
            this.renderFileList();
        }
        
        async uploadFiles() {
            if (this.files.length === 0 || this.uploading) return;
            
            this.uploading = true;
            this.progressBar.style.display = 'block';
            
            const uploadedFiles = [];
            
            for (let i = 0; i < this.files.length; i++) {
                const file = this.files[i];
                const progress = ((i + 1) / this.files.length) * 100;
                
                this.progressFill.style.width = `${progress}%`;
                this.progressText.textContent = `Uploading ${i + 1}/${this.files.length}...`;
                
                try {
                    const result = await this.uploadFile(file);
                    uploadedFiles.push(result);
                } catch (error) {
                    console.error('Upload failed:', error);
                    alert(`Failed to upload "${file.name}": ${error.message}`);
                }
            }
            
            this.progressBar.style.display = 'none';
            this.uploading = false;
            this.files = [];
            this.renderFileList();
            
            // Notify parent about completed uploads
            if (this.onUploadComplete && uploadedFiles.length > 0) {
                this.onUploadComplete(uploadedFiles);
            }
        }
        
        async uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(CONFIG.uploadUrl, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            
            // Read response text once
            const text = await response.text();
            
            if (!response.ok) {
                // Try to parse error as JSON
                try {
                    const error = JSON.parse(text);
                    throw new Error(error.error || `Upload failed (${response.status})`);
                } catch (e) {
                    // If not JSON, check if it's a login redirect
                    if (text.includes('login') || text.includes('Log In')) {
                        throw new Error('Please log in to upload files');
                    }
                    throw new Error(`Upload failed (${response.status}): ${text.substring(0, 100)}`);
                }
            }
            
            // Try to parse as JSON
            try {
                return JSON.parse(text);
            } catch (e) {
                throw new Error(`Invalid response format: ${text.substring(0, 100)}`);
            }
        }
        
        formatSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
    }
    
    // Auto-initialize if data attribute is present
    document.addEventListener('DOMContentLoaded', () => {
        const uploadContainers = document.querySelectorAll('[data-file-upload]');
        uploadContainers.forEach(container => {
            const options = JSON.parse(container.dataset.fileUpload || '{}');
            window.fileUpload = new FileUploadComponent(container.id, options);
        });
    });
    
    // Export for manual initialization
    window.FileUploadComponent = FileUploadComponent;
})();
