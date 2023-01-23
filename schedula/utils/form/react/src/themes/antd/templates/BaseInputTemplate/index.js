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
    const {format, inputProps: extraInputProps} = options
    const {readonlyAsDisabled = true} = formContext;


    const handleNumberChange = (nextValue) => onChange(nextValue);
    const handleTextChange = onChangeOverride
        ? onChangeOverride
        : ({target}) => onChange(target.value === '' ? options.emptyValue : target.value);

    const handleBlur = ({target}) => onBlur(id, target.value);

    const handleFocus = ({target}) => {
        onFocus(id, target.value)
    };
    const input = inputType === 'number' || inputType === 'integer' ?
        <InputNumber
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onBlur={!readonly ? handleBlur : undefined}
            onChange={!readonly ? handleNumberChange : undefined}
            onFocus={!readonly ? handleFocus : undefined}
            placeholder={placeholder}
            format={format}
            style={INPUT_STYLE}
            emptyValue={Array.isArray(schema.type) ? ('null' in schema.type ? null : ('string' in schema.type ? '' : 0)) : 0}
            list={schema.examples ? examplesId(id) : undefined}
            {...inputProps}
            {...extraInputProps}
            value={value}
            aria-describedby={ariaDescribedByIds(id, !!schema.examples)}/>
        :
        <Input
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onBlur={!readonly ? handleBlur : undefined}
            onChange={!readonly ? handleTextChange : undefined}
            onFocus={!readonly ? handleFocus : undefined}
            placeholder={placeholder}
            style={INPUT_STYLE}
            list={schema.examples ? examplesId(id) : undefined}
            type={inputType}
            {...inputProps}
            {...extraInputProps}
            value={value}
            aria-describedby={ariaDescribedByIds(id, !!schema.examples)}/>;
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
