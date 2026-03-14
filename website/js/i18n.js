// Internationalization for MRRC Website
const i18n = {
    zh: {
        nav: {
            features: '功能特性',
            demo: '在线演示',
            docs: '文档',
            install: '安装指南'
        },
        hero: {
            badge: '业余无线电的革命',
            title: '随时随地<br>掌控您的电台',
            subtitle: 'MRRC (Mobile Remote Radio Control) 是一款专为HAM Radio爱好者设计的现代Web远程控制系统。支持手机、平板、电脑访问，超低延迟音频传输，专业级DSP降噪，让短波通信无处不在。',
            try_now: '立即体验',
            view_github: '查看源码',
            latency: '延迟',
            ptt_reliability: 'PTT可靠性',
            mobile_support: '移动支持'
        },
        features: {
            title: '核心功能',
            subtitle: '为现代HAM Radio操作优化的完整解决方案',
            mobile: {
                title: '移动优先设计',
                desc: '专为触摸屏优化的界面，PWA支持离线访问，iPhone/Android完美适配，随时随地操作电台。'
            },
            low_latency: {
                title: '超低延迟',
                desc: 'TX/RX切换 < 100ms，Opus编码优化，AudioWorklet播放，WDSP降噪，专业级实时体验。'
            },
            dsp: {
                title: '专业DSP',
                desc: '集成WDSP库，支持NR2频谱降噪、噪声抑制、自动陷波、AGC，短波语音更清晰。'
            },
            security: {
                title: '安全可靠',
                desc: 'TLS加密传输，用户认证保护，完整的安全机制，让您的电台安全接入互联网。'
            },
            control: {
                title: '完整控制',
                desc: '频率、模式、PTT、滤波器、天调，完整的电台控制功能，支持Hamlib/rigctld。'
            },
            atr1000: {
                title: 'ATR-1000集成',
                desc: '实时功率/SWR显示，自动天调存储，智能频率跟随，天调参数自动学习。'
            },
            voice: {
                title: '语音助手',
                desc: 'AI语音识别与合成，语音控制电台，呼号自动解释法转换，智能对话交互。'
            },
            panadapter: {
                title: '频谱显示',
                desc: '实时频谱分析，FFT瀑布图，信号强度显示，可视化信号监测。'
            }
        },
        demo: {
            title: '在线演示',
            subtitle: '体验现代HAM Radio控制界面',
            mobile: '移动端界面',
            voice: '语音助手',
            recordings: '录音回放',
            notice: '演示站点需要有效的HAM Radio执照和授权访问'
        },
        tech: {
            title: '技术架构'
        },
        cta: {
            title: '准备好开始了吗？',
            subtitle: '加入全球HAM Radio爱好者，体验现代化的远程电台控制',
            get_started: '开始使用',
            read_docs: '阅读文档'
        },
        footer: {
            desc: 'Mobile Remote Radio Control - 现代HAM Radio的远程控制解决方案',
            links: '链接',
            features: '功能特性',
            docs: '文档',
            install: '安装',
            community: '社区',
            issues: '问题反馈',
            discussions: '讨论',
            wiki: 'Wiki',
            license: '开源许可：GPL-3.0'
        }
    },
    en: {
        nav: {
            features: 'Features',
            demo: 'Live Demo',
            docs: 'Documentation',
            install: 'Installation'
        },
        hero: {
            badge: 'Revolution in Amateur Radio',
            title: 'Control Your Radio<br>Anytime, Anywhere',
            subtitle: 'MRRC (Mobile Remote Radio Control) is a modern Web-based remote control system designed for HAM Radio enthusiasts. Supports mobile phones, tablets, and computers with ultra-low latency audio transmission and professional-grade DSP noise reduction, making HF communication accessible everywhere.',
            try_now: 'Try It Now',
            view_github: 'View on GitHub',
            latency: 'Latency',
            ptt_reliability: 'PTT Reliability',
            mobile_support: 'Mobile Support'
        },
        features: {
            title: 'Key Features',
            subtitle: 'Complete solution optimized for modern HAM Radio operations',
            mobile: {
                title: 'Mobile-First Design',
                desc: 'Touch-optimized interface, PWA offline support, perfect for iPhone/Android. Control your radio from anywhere, anytime.'
            },
            low_latency: {
                title: 'Ultra Low Latency',
                desc: 'TX/RX switching < 100ms, Opus codec optimization, AudioWorklet playback, WDSP noise reduction. Professional real-time experience.'
            },
            dsp: {
                title: 'Professional DSP',
                desc: 'Integrated WDSP library with NR2 spectral noise reduction, noise blanker, auto notch filter, AGC. Clearer HF voice communication.'
            },
            security: {
                title: 'Secure & Reliable',
                desc: 'TLS encrypted transmission, user authentication protection, complete security mechanisms for safe internet-connected radio access.'
            },
            control: {
                title: 'Full Control',
                desc: 'Frequency, mode, PTT, filters, antenna tuner - complete radio control functions with Hamlib/rigctld support.'
            },
            atr1000: {
                title: 'ATR-1000 Integration',
                desc: 'Real-time power/SWR display, automatic antenna tuner memory, intelligent frequency following, auto-learning tuner parameters.'
            },
            voice: {
                title: 'Voice Assistant',
                desc: 'AI speech recognition and synthesis, voice-controlled radio operations, automatic callsign phonetic conversion, intelligent dialogue interaction.'
            },
            panadapter: {
                title: 'Panadapter Display',
                desc: 'Real-time spectrum analysis, FFT waterfall, signal strength display, visual signal monitoring.'
            }
        },
        demo: {
            title: 'Live Demo',
            subtitle: 'Experience the modern HAM Radio control interface',
            mobile: 'Mobile Interface',
            voice: 'Voice Assistant',
            recordings: 'Recordings',
            notice: 'Demo site requires valid HAM Radio license and authorized access'
        },
        tech: {
            title: 'Technology Stack'
        },
        cta: {
            title: 'Ready to Get Started?',
            subtitle: 'Join HAM Radio enthusiasts worldwide and experience modern remote radio control',
            get_started: 'Get Started',
            read_docs: 'Read Documentation'
        },
        footer: {
            desc: 'Mobile Remote Radio Control - Modern remote control solution for HAM Radio',
            links: 'Links',
            features: 'Features',
            docs: 'Documentation',
            install: 'Installation',
            community: 'Community',
            issues: 'Issues',
            discussions: 'Discussions',
            wiki: 'Wiki',
            license: 'Open Source License: GPL-3.0'
        }
    }
};

let currentLang = 'zh';

function toggleLanguage() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    updateLanguage();
    localStorage.setItem('mrrc-lang', currentLang);
}

function updateLanguage() {
    const texts = i18n[currentLang];
    document.querySelector('.current-lang').textContent = currentLang === 'zh' ? '中文' : 'EN';
    
    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        const keys = key.split('.');
        let value = texts;
        
        for (const k of keys) {
            if (value && value[k]) {
                value = value[k];
            } else {
                value = null;
                break;
            }
        }
        
        if (value) {
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.placeholder = value;
            } else {
                element.innerHTML = value;
            }
        }
    });
    
    // Update HTML lang attribute
    document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
}

// Initialize language on page load
document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('mrrc-lang');
    if (savedLang && i18n[savedLang]) {
        currentLang = savedLang;
    }
    updateLanguage();
});
