import type { CSSProperties } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';

export type CommonPrompt = { label: string; text: string };

const MAX_ITEMS = 20;

export function normalizeCommonPrompts(raw: unknown): CommonPrompt[] {
    if (!Array.isArray(raw)) return [];
    const out: CommonPrompt[] = [];
    for (const p of raw) {
        if (typeof p === 'string') {
            const text = p.trim();
            if (!text) continue;
            out.push({ label: text.length > 48 ? `${text.slice(0, 48)}…` : text, text: text.slice(0, 4000) });
        } else if (p && typeof p === 'object') {
            const text = String((p as { text?: string }).text ?? '').trim();
            if (!text) continue;
            let label = String((p as { label?: string }).label ?? '').trim();
            if (!label) label = text.length > 40 ? `${text.slice(0, 40)}…` : text;
            out.push({ label: label.slice(0, 80), text: text.slice(0, 4000) });
        }
        if (out.length >= MAX_ITEMS) break;
    }
    return out;
}

export function promptsEqual(a: CommonPrompt[], b: CommonPrompt[]): boolean {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i].label !== b[i].label || a[i].text !== b[i].text) return false;
    }
    return true;
}

type TipState = { text: string; left: number; top: number; maxW: number } | null;

export function CommonPromptStrip({
    prompts,
    onPick,
    disabled,
}: {
    prompts: CommonPrompt[];
    onPick: (text: string) => void;
    disabled?: boolean;
}) {
    const { t } = useTranslation();
    const [tip, setTip] = useState<TipState>(null);

    const showTip = useCallback((el: HTMLElement, text: string) => {
        const r = el.getBoundingClientRect();
        const maxW = Math.min(480, Math.max(240, window.innerWidth - r.left - 16));
        setTip({
            text,
            left: r.left,
            top: r.bottom + 8,
            maxW,
        });
    }, []);

    const hideTip = useCallback(() => setTip(null), []);

    useEffect(() => {
        if (!tip) return;
        const hide = () => setTip(null);
        window.addEventListener('scroll', hide, true);
        window.addEventListener('resize', hide);
        return () => {
            window.removeEventListener('scroll', hide, true);
            window.removeEventListener('resize', hide);
        };
    }, [tip]);

    if (!prompts.length) return null;

    const tipLayer =
        tip &&
        createPortal(
            <div
                role="tooltip"
                style={{
                    position: 'fixed',
                    left: tip.left,
                    top: tip.top,
                    maxWidth: tip.maxW,
                    maxHeight: 'min(50vh, 320px)',
                    overflow: 'auto',
                    padding: '10px 12px',
                    zIndex: 20000,
                    fontSize: '12px',
                    lineHeight: 1.5,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: 'var(--text-primary)',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-default)',
                    borderRadius: '10px',
                    boxShadow: '0 12px 40px rgba(0,0,0,0.35)',
                    pointerEvents: 'none',
                }}
            >
                {tip.text}
            </div>,
            document.body,
        );

    return (
        <div style={{ padding: '4px 0 8px', flexShrink: 0, width: '100%' }}>
            {tipLayer}
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '6px' }}>
                {t('agent.chat.commonPromptsHint')}
            </div>
            <div
                style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '6px',
                    alignItems: 'center',
                    maxHeight: '120px',
                    overflowY: 'auto',
                }}
            >
                {prompts.map((p, i) => (
                    <button
                        key={`${i}-${p.label.slice(0, 12)}`}
                        type="button"
                        disabled={disabled}
                        onClick={() => onPick(p.text)}
                        onMouseEnter={(e) => !disabled && showTip(e.currentTarget, p.text)}
                        onMouseLeave={hideTip}
                        onFocus={(e) => !disabled && showTip(e.currentTarget, p.text)}
                        onBlur={hideTip}
                        style={{
                            maxWidth: '100%',
                            padding: '5px 10px',
                            borderRadius: '8px',
                            border: '1px solid color-mix(in srgb, var(--border-subtle) 70%, var(--accent-primary))',
                            background: 'color-mix(in srgb, var(--bg-secondary) 92%, var(--accent-primary) 8%)',
                            color: 'var(--text-primary)',
                            fontSize: '12px',
                            fontWeight: 500,
                            cursor: disabled ? 'not-allowed' : 'pointer',
                            opacity: disabled ? 0.55 : 1,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            lineHeight: 1.3,
                        }}
                    >
                        {p.label}
                    </button>
                ))}
            </div>
        </div>
    );
}

function CommonPromptFormModal({
    open,
    mode,
    initial,
    onSave,
    onDelete,
    onClose,
}: {
    open: boolean;
    mode: 'add' | 'edit';
    initial: CommonPrompt;
    onSave: (item: CommonPrompt) => void;
    onDelete?: () => void;
    onClose: () => void;
}) {
    const { t } = useTranslation();
    const [label, setLabel] = useState('');
    const [text, setText] = useState('');
    const [err, setErr] = useState('');
    const overlayRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (open) {
            setLabel(initial.label);
            setText(initial.text);
            setErr('');
        }
    }, [open, initial.label, initial.text]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKey);
        overlayRef.current?.focus();
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);

    if (!open) return null;

    const handleSave = () => {
        const ttrim = text.trim();
        if (!ttrim) {
            setErr(t('agent.settings.commonPromptsTextRequired'));
            return;
        }
        onSave({ label: label.trim().slice(0, 80), text: ttrim.slice(0, 4000) });
        onClose();
    };

    return (
        <div
            ref={overlayRef}
            tabIndex={-1}
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.45)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 12000,
                padding: '16px',
                outline: 'none',
            }}
            onClick={(e) => {
                if (e.target === e.currentTarget) onClose();
            }}
            role="presentation"
        >
            <div
                className="card"
                style={{
                    width: '100%',
                    maxWidth: '480px',
                    maxHeight: '90vh',
                    overflow: 'auto',
                    margin: 0,
                    padding: '20px',
                    border: '1px solid var(--border-subtle)',
                    boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                <h4 style={{ margin: '0 0 14px', fontSize: '16px', fontWeight: 600 }}>
                    {mode === 'add'
                        ? t('agent.settings.commonPromptsModalAddTitle')
                        : t('agent.settings.commonPromptsModalEditTitle')}
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div>
                        <label className="form-label" style={{ display: 'block', marginBottom: '6px', fontSize: '13px' }}>
                            {t('agent.settings.commonPromptsLabelPh')}
                        </label>
                        <input
                            className="input"
                            value={label}
                            onChange={(e) => setLabel(e.target.value)}
                            maxLength={80}
                            placeholder={t('agent.settings.commonPromptsLabelPh')}
                            style={{ width: '100%' }}
                            autoFocus
                        />
                    </div>
                    <div>
                        <label className="form-label" style={{ display: 'block', marginBottom: '6px', fontSize: '13px' }}>
                            {t('agent.settings.commonPromptsTextPh')}
                        </label>
                        <textarea
                            className="input"
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            maxLength={4000}
                            rows={8}
                            placeholder={t('agent.settings.commonPromptsTextPh')}
                            style={{ width: '100%', resize: 'vertical', minHeight: '140px', fontFamily: 'inherit' }}
                        />
                    </div>
                    {err && (
                        <div style={{ fontSize: '12px', color: 'var(--error)' }}>{err}</div>
                    )}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '18px', gap: '10px', flexWrap: 'wrap' }}>
                    <div>
                        {mode === 'edit' && onDelete && (
                            <button type="button" className="btn btn-secondary" style={{ color: 'var(--error)' }} onClick={onDelete}>
                                {t('agent.settings.commonPromptsModalDelete')}
                            </button>
                        )}
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <button type="button" className="btn btn-secondary" onClick={onClose}>
                            {t('common.cancel')}
                        </button>
                        <button type="button" className="btn btn-primary" onClick={handleSave}>
                            {t('agent.settings.commonPromptsModalConfirm')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export function CommonPromptsEditor({
    value,
    onChange,
    disabled,
}: {
    value: CommonPrompt[];
    onChange: (next: CommonPrompt[]) => void;
    disabled?: boolean;
}) {
    const { t } = useTranslation();
    const [modalOpen, setModalOpen] = useState(false);
    const [modalMode, setModalMode] = useState<'add' | 'edit'>('add');
    const [editIndex, setEditIndex] = useState<number | null>(null);
    const [draftInitial, setDraftInitial] = useState<CommonPrompt>({ label: '', text: '' });

    const openAdd = () => {
        if (value.length >= MAX_ITEMS || disabled) return;
        setModalMode('add');
        setEditIndex(null);
        setDraftInitial({ label: '', text: '' });
        setModalOpen(true);
    };

    const openEdit = (idx: number) => {
        const row = value[idx];
        if (!row || disabled) return;
        setModalMode('edit');
        setEditIndex(idx);
        setDraftInitial({ label: row.label, text: row.text });
        setModalOpen(true);
    };

    const closeModal = () => setModalOpen(false);

    const handleSave = (item: CommonPrompt) => {
        if (modalMode === 'add') {
            onChange([...value, item]);
        } else if (editIndex !== null) {
            const next = value.map((row, i) => (i === editIndex ? item : row));
            onChange(next);
        }
    };

    const handleDelete = () => {
        if (editIndex === null) return;
        onChange(value.filter((_, i) => i !== editIndex));
        closeModal();
    };

    const preview = (txt: string, max = 72) => {
        const s = txt.replace(/\s+/g, ' ').trim();
        if (s.length <= max) return s || '—';
        return `${s.slice(0, max)}…`;
    };

    return (
        <div>
            <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '12px' }}>
                {t('agent.settings.commonPromptsDesc')}
            </p>
            <div
                style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '10px',
                    alignItems: 'stretch',
                }}
            >
                {value.map((row, idx) => (
                    <button
                        key={idx}
                        type="button"
                        disabled={disabled}
                        title={row.text}
                        onClick={() => openEdit(idx)}
                        style={{
                            textAlign: 'left',
                            width: 'min(100%, 200px)',
                            minHeight: '88px',
                            padding: '10px 12px',
                            borderRadius: '10px',
                            border: '1px solid color-mix(in srgb, var(--border-subtle) 70%, var(--accent-primary))',
                            background: 'color-mix(in srgb, var(--bg-secondary) 94%, var(--accent-primary) 6%)',
                            cursor: disabled ? 'not-allowed' : 'pointer',
                            opacity: disabled ? 0.65 : 1,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '6px',
                        }}
                    >
                        <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.3 }}>
                            {row.label.trim() || preview(row.text, 24)}
                        </span>
                        <span
                            style={{
                                fontSize: '11px',
                                color: 'var(--text-tertiary)',
                                lineHeight: 1.45,
                                display: '-webkit-box',
                                WebkitLineClamp: 3,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                            } as CSSProperties}
                        >
                            {preview(row.text, 140)}
                        </span>
                    </button>
                ))}
            </div>
            <button
                type="button"
                className="btn btn-secondary"
                style={{ marginTop: '14px' }}
                disabled={disabled || value.length >= MAX_ITEMS}
                onClick={openAdd}
            >
                {t('agent.settings.commonPromptsAdd')}
            </button>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '8px' }}>
                {t('agent.settings.commonPromptsLimit', { max: MAX_ITEMS })}
            </div>

            <CommonPromptFormModal
                open={modalOpen}
                mode={modalMode}
                initial={draftInitial}
                onSave={handleSave}
                onDelete={modalMode === 'edit' ? handleDelete : undefined}
                onClose={closeModal}
            />
        </div>
    );
}
