import {useState, useMemo} from 'react'
import {Input} from 'antd';
import InputNumber from './number';
import {
    ariaDescribedByIds,
    examplesId,
    getInputProps,
} from '@rjsf/utils';
import debounce from "lodash/debounce";

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
    let {
        format,
        emptyValue = '',
        inputProps: _inputProps,
        ...extraInputProps
    } = options
    extraInputProps = {..._inputProps, ...extraInputProps}
    const {readonlyAsDisabled = true} = formContext;
    const [editedValue, setEditedValue] = useState(undefined)

    const textChange = useMemo(() => (debounce((value) => {
        onChange(value)
    }, 500)), [onChange]);

    const _clean = useMemo(() => (debounce(() => {
        setEditedValue(undefined)
    }, 1000)), [setEditedValue]);


    const handleBlur = ({target: {value}}) => {
        onBlur(id, value)
        _clean()
    };
    const handleFocus = ({target: {value}}) => {
        onFocus(id, value)
    };
    const handleChange = ({target: {value}}) => {
        let nextValue = value === '' ? emptyValue : value
        setEditedValue(nextValue);
        textChange(nextValue);
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
