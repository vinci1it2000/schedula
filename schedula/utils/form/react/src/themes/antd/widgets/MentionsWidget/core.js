import React, {useEffect, useState} from "react";
import {Mentions} from "antd";
import {ariaDescribedByIds} from "@rjsf/utils";

export default function MentionsWidget(props) {
    const {
        autofocus,
        disabled,
        formContext,
        id,
        onBlur,
        onChange,
        onFocus,
        options,
        readonly,
        value,
    } = props;
    const {readonlyAsDisabled = true} = formContext;
    const [editedValue, setEditedValue] = useState(undefined)
    const textChange = (nextValue) => onChange(nextValue);

    const _onChange = () => {
        if (editedValue !== undefined)
            textChange(editedValue)
    };
    const [timeoutId, setTimeoutId] = useState(undefined)
    useEffect(() => {
        if (timeoutId !== undefined)
            clearTimeout(timeoutId)
        setTimeoutId(setTimeout(() => {
            _onChange()
        }, 500));
    }, [editedValue])

    const handleBlur = () => {
        _onChange();
        setEditedValue(undefined)
        onBlur(id, value)
    };

    const handleChange = (nextValue) => {
        setEditedValue(nextValue);
    }

    const handleFocus = () => onFocus(id, value);

    const {mentions, ...opt} = options
    const extraProps = {
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
        ...opt
    };

    return (
        <Mentions
            autoFocus={autofocus}
            value={editedValue === undefined ? value : editedValue}
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onChange={!readonly ? handleChange : undefined}
            options={mentions.map((value) => ({
                key: value,
                value,
                label: value,
            }))}
            {...extraProps}
            aria-describedby={ariaDescribedByIds(id)}>
        </Mentions>
    );
}