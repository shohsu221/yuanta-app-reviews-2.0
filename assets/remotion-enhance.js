(function () {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hasGsap = Boolean(window.gsap);

    const RemotionMotion = {
        fps: 30,
        frame: 0,
        clamp(value, min, max) {
            return Math.min(max, Math.max(min, value));
        },
        interpolate(frame, inputRange, outputRange) {
            const [inMin, inMax] = inputRange;
            const [outMin, outMax] = outputRange;
            const progress = this.clamp((frame - inMin) / (inMax - inMin), 0, 1);
            return outMin + (outMax - outMin) * progress;
        },
        spring(frame, damping = 14, mass = 1) {
            const t = frame / this.fps;
            return 1 - Math.exp(-damping * t / mass) * Math.cos(12 * t);
        },
        easeOutQuart(t) {
            return 1 - Math.pow(1 - t, 4);
        },
    };

    window.RemotionMotion = RemotionMotion;

    if (hasGsap) {
        gsap.defaults({ ease: 'expo.out', duration: 0.24, overwrite: 'auto' });
    }

    if (window.Chart) {
        Chart.defaults.animation = {
            duration: prefersReduced ? 0 : 420,
            easing: 'easeOutQuart',
            delay(context) {
                return prefersReduced ? 0 : Math.min(180, context.dataIndex * 24 + context.datasetIndex * 50);
            },
        };
        Chart.defaults.plugins.tooltip.backgroundColor = '#061b31';
        Chart.defaults.plugins.tooltip.borderColor = '#d6d9fc';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.color = '#64748d';
    }

    function prepareScenes() {
        const sceneSelector = [
            'header',
            '#content-dashboard > section',
            '#content-reviews > section',
            '#content-expert > section',
            'footer',
        ].join(',');

        const scenes = Array.from(document.querySelectorAll(sceneSelector));
        const uniqueScenes = [...new Set(scenes)];
        uniqueScenes.forEach((node, index) => {
            node.classList.add('rm-scene');
            node.style.setProperty('--rm-stagger', `${Math.min(index * 16, 120)}ms`);
        });

        const bars = Array.from(document.querySelectorAll('[style*="width:"]'))
            .filter((node) => node.className && String(node.className).includes('rounded-full'));
        bars.forEach((bar) => bar.classList.add('rm-bar'));

        if (prefersReduced) {
            uniqueScenes.forEach((node) => node.classList.add('rm-visible'));
            bars.forEach((bar) => bar.classList.add('rm-visible'));
            return;
        }

        if (hasGsap) {
            gsap.set(uniqueScenes, { autoAlpha: 0, y: 8 });
            gsap.set(bars, { scaleX: 0.08, transformOrigin: 'left center' });
        }

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                if (hasGsap) {
                    const barsInScene = entry.target.querySelectorAll('.rm-bar');
                    const tl = gsap.timeline();
                    tl.to(entry.target, { autoAlpha: 1, y: 0, duration: 0.24 }, 0);
                    if (barsInScene.length) {
                        tl.to(barsInScene, {
                            scaleX: 1,
                            duration: 0.36,
                            stagger: 0.035,
                        }, 0.08);
                    }
                } else {
                    entry.target.classList.add('rm-visible');
                    entry.target.querySelectorAll('.rm-bar').forEach((bar) => bar.classList.add('rm-visible'));
                }
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -4% 0px' });

        uniqueScenes.forEach((node) => observer.observe(node));
    }

    function animateMetricNumbers() {
        if (prefersReduced) return;
        const candidates = Array.from(document.querySelectorAll('.text-2xl, .text-3xl, .text-5xl'))
            .filter((node) => /^\d+(\.\d+)?%?$/.test(node.textContent.trim()));

        candidates.forEach((node) => {
            const raw = node.textContent.trim();
            const isPercent = raw.endsWith('%');
            const decimals = raw.includes('.') ? raw.split('.')[1].replace('%', '').length : 0;
            const target = Number(raw.replace('%', ''));
            if (!Number.isFinite(target)) return;

            if (hasGsap) {
                const state = { value: 0 };
                gsap.to(state, {
                    value: target,
                    duration: 0.36,
                    ease: 'power4.out',
                    onUpdate() {
                        node.textContent = `${state.value.toFixed(decimals)}${isPercent ? '%' : ''}`;
                    },
                });
                return;
            }

            let start = null;
            const duration = 360;
            const render = (timestamp) => {
                if (start === null) start = timestamp;
                const elapsed = timestamp - start;
                const progress = RemotionMotion.easeOutQuart(RemotionMotion.clamp(elapsed / duration, 0, 1));
                const value = target * progress;
                node.textContent = `${value.toFixed(decimals)}${isPercent ? '%' : ''}`;
                if (elapsed < duration) requestAnimationFrame(render);
            };
            requestAnimationFrame(render);
        });
    }

    function enhanceTabs() {
        if (prefersReduced || !hasGsap || typeof window.switchTab !== 'function') return;
        const originalSwitchTab = window.switchTab;
        window.switchTab = async function gsapSwitchTab(tabId) {
            const entering = document.getElementById(
                tabId === 'dashboard'
                    ? 'content-dashboard'
                    : tabId === 'reviews'
                        ? 'content-reviews'
                        : 'content-expert',
            );
            await originalSwitchTab(tabId);
            if (!entering) return;
            const barsInTab = entering.querySelectorAll('.rm-bar');
            gsap.fromTo(
                entering,
                { autoAlpha: 0, y: 6 },
                { autoAlpha: 1, y: 0, duration: 0.22, ease: 'expo.out' },
            );
            if (barsInTab.length) {
                gsap.to(barsInTab, {
                    scaleX: 1,
                    duration: 0.28,
                    stagger: 0.025,
                    transformOrigin: 'left center',
                });
            }
        };
    }

    function enhanceHeroTilt() {
        if (prefersReduced || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
        const hero = document.querySelector('header.hero-3d-card');
        if (!hero) return;

        const maxTiltX = 4.5;
        const maxTiltY = 7;
        let frame = null;
        let targetX = 0;
        let targetY = 0;

        const applyTilt = () => {
            frame = null;
            hero.style.setProperty('--hero-tilt-x', `${targetX.toFixed(2)}deg`);
            hero.style.setProperty('--hero-tilt-y', `${targetY.toFixed(2)}deg`);
        };

        hero.addEventListener('mousemove', (event) => {
            const rect = hero.getBoundingClientRect();
            const px = (event.clientX - rect.left) / rect.width - 0.5;
            const py = (event.clientY - rect.top) / rect.height - 0.5;
            targetX = (-py * maxTiltX * 2);
            targetY = (px * maxTiltY * 2);
            if (!frame) frame = requestAnimationFrame(applyTilt);
        });

        hero.addEventListener('mouseleave', () => {
            targetX = 0;
            targetY = 0;
            if (!frame) frame = requestAnimationFrame(applyTilt);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.documentElement.dataset.motion = hasGsap ? 'gsap-enhanced' : 'remotion-enhanced';
        document.documentElement.dataset.theme = 'impeccable';
        prepareScenes();
        animateMetricNumbers();
        enhanceTabs();
        enhanceHeroTilt();
    });
})();
