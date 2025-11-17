// ATU状态显示框动态定位
// 将ATU状态显示框定位到TX按钮左边、频谱显示下边

class AtuPositioning {
    constructor() {
        this.atuStatusDiv = null;
        this.txButton = null;
        this.spectrumCanvas = null;
        this.initialized = false;
        
        this.init();
    }
    
    init() {
        // 等待页面加载完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.positionAtuStatus());
        } else {
            this.positionAtuStatus();
        }
        
        // 监听窗口大小变化
        window.addEventListener('resize', () => this.positionAtuStatus());
    }
    
    positionAtuStatus() {
        // 获取ATU状态显示框
        this.atuStatusDiv = document.getElementById('div-atu-status');
        if (!this.atuStatusDiv) {
            console.log('ATU状态显示框未找到，等待重试...');
            setTimeout(() => this.positionAtuStatus(), 100);
            return;
        }
        
        // 获取TX按钮
        this.txButton = document.getElementById('TX-record');
        if (!this.txButton) {
            console.log('TX按钮未找到，等待重试...');
            setTimeout(() => this.positionAtuStatus(), 100);
            return;
        }
        
        // 获取频谱显示canvas
        this.spectrumCanvas = document.getElementById('canBFFFT');
        if (!this.spectrumCanvas) {
            console.log('频谱显示canvas未找到，等待重试...');
            setTimeout(() => this.positionAtuStatus(), 100);
            return;
        }
        
        // 计算位置
        this.calculateAndSetPosition();
        
        if (!this.initialized) {
            console.log('✅ ATU状态显示框定位完成');
            this.initialized = true;
        }
    }
    
    calculateAndSetPosition() {
        // 获取TX按钮的位置和尺寸
        const txRect = this.txButton.getBoundingClientRect();
        
        // 获取频谱显示canvas的位置和尺寸
        const spectrumRect = this.spectrumCanvas.getBoundingClientRect();
        
        // 计算ATU状态显示框的位置
        let left, top;
        
        // 目标位置：与TX按钮同高度，左右位置与频谱显示框对齐
        // 计算左右位置：与频谱显示框左对齐
        left = spectrumRect.left;
        
        // 计算高度位置：与TX按钮同高度
        top = txRect.top;
        
        // 如果ATU框与频谱显示框重叠，则调整位置
        if (top + 200 > spectrumRect.top && top < spectrumRect.bottom) {
            // 如果重叠，将ATU框放在频谱显示框下方
            top = spectrumRect.bottom + 10;
        }
        
        // 确保位置在可视区域内
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // 边界检查
        if (left < 10) left = 10;
        if (left + 450 > viewportWidth) left = viewportWidth - 460;
        if (top < 10) top = 10;
        if (top + 200 > viewportHeight) top = viewportHeight - 210;
        
        // 应用位置
        this.atuStatusDiv.style.position = 'fixed';
        this.atuStatusDiv.style.left = left + 'px';
        this.atuStatusDiv.style.top = top + 'px';
        this.atuStatusDiv.style.width = '450px';
        this.atuStatusDiv.style.height = '200px';
        this.atuStatusDiv.style.zIndex = '1000';
        this.atuStatusDiv.style.display = 'block';
        
        console.log(`📍 ATU状态显示框位置: left=${left}px, top=${top}px`);
        console.log(`📍 TX按钮位置: left=${txRect.left}px, top=${txRect.top}px`);
        console.log(`📍 频谱显示位置: bottom=${spectrumRect.bottom}px`);
    }
}

// 初始化ATU定位系统
window.addEventListener('load', () => {
    new AtuPositioning();
});

// 提供全局函数用于手动重新定位
function repositionAtuStatus() {
    const positioning = new AtuPositioning();
    positioning.positionAtuStatus();
}