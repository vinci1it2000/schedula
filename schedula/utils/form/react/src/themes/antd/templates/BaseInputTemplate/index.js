import {useState, useEffect} from 'react'
import Input from 'antd/lib/input';
import InputNumber from './number';
import {
    ariaDescribedByIds,
    examplesId,
    getInputProps,
} from '@rjsf/utils';

const INPUT_STYLE = {
    width: '100%',
};

export default function BaseInputTemplate(props) {
    const {
        disabled,
        formContext,
        id,
        onBlur,
        onChange,
        onChangeOverride,
        onFocus,
        options,
        placeholder,
        readonly,
        schema,
        value,
        type,
    } = props;
    const {type: inputType, ...inputProps} = getInputProps({
        ...schema,
        type: Array.isArray(schema.type) ? schema.type[0] : schema.type
    }, type, options, false);
    const {format, inputProps: extraInputProps, emptyValue = ''} = options
    const {readonlyAsDisabled = true} = formContext;
    const [editedValue, setEditedValue] = useState(undefined)

    const textChange = ({target: {value}}) => onChange(value === '' ? emptyValue : value);

    const _onChange = () => {
        if (editedValue !== undefined) {
            if (inputType === 'number' || inputType === 'integer') {
                onChange(editedValue)
            } else {
                (onChangeOverride || textChange)({target: {value: editedValue}})
            }
        }
    };
    const [timeoutId, setTimeoutId] = useState(undefined)
    useEffect(() => {
        if (timeoutId !== undefined)
            clearTimeout(timeoutId)
        setTimeoutId(setTimeout(() => {
            _onChange()
        }, 500));
    }, [editedValue])

    const handleBlur = ({target: {value}}) => {
        _onChange();
        setEditedValue(undefined)
        onBlur(id, value)
    };
    const handleFocus = ({target: {value}}) => {
        onFocus(id, value)
    };
    const handleChange = ({target: {value}}) => {
        setEditedValue(value === '' ? emptyValue : value);
    }
    let input;
    if (inputType === 'number' || inputType === 'integer') {
        input = <InputNumber
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onBlur={!readonly ? handleBlur : undefined}
            onChange={!readonly ? (nextValue => handleChange({target: {value: nextValue}})) : undefined}
            onFocus={!readonly ? handleFocus : undefined}
            placeholder={placeholder}
            format={format}
            style={INPUT_STYLE}
            emptyValue={Array.isArray(schema.type) ? ('null' in schema.type ? null : ('string' in schema.type ? '' : 0)) : 0}
            list={schema.examples ? examplesId(id) : undefined}
            {...inputProps}
            {...extraInputProps}
            value={editedValue === undefined ? value : editedValue}
            aria-describedby={ariaDescribedByIds(id, !!schema.examples)}/>
    } else {
        input = <Input
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onBlur={!readonly ? handleBlur : undefined}
            onChange={!readonly ? handleChange : undefined}
            onFocus={!readonly ? handleFocus : undefined}
            placeholder={placeholder}
            style={INPUT_STYLE}
            list={schema.examples ? examplesId(id) : undefined}
            type={inputType}
            {...inputProps}
            {...extraInputProps}
            value={editedValue === undefined ? value : editedValue}
            aria-describedby={ariaDescribedByIds(id, !!schema.examples)}/>;
    }
    return <>
        {input}
        {Array.isArray(schema.examples) && (
            <datalist id={examplesId(id)}>
                {(schema.examples)
                    .concat(schema.default && !schema.examples.includes(schema.default) ? ([schema.default]) : [])
                    .map((example) => {
                        return <option key={example} value={example}/>;
                    })}
            </datalist>
        )}
    </>
}
