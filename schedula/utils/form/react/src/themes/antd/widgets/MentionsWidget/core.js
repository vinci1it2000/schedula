import React, {useMemo, useState} from "react";
import {Mentions} from "antd";
import {ariaDescribedByIds} from "@rjsf/utils";
import debounce from "lodash/debounce";

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

    const textChange = useMemo(() => (debounce((nextValue) => {
        onChange(nextValue)
    }, 500)), [onChange]);

    const _clean = useMemo(() => (debounce(() => {
        setEditedValue(undefined)
    }, 1000)), [setEditedValue]);

    const handleBlur = () => {
        onBlur(id, value)
        _clean();
    };

    const handleChange = (nextValue) => {
        setEditedValue(nextValue);
        textChange(nextValue);
    }

    const handleFocus = () => onFocus(id, value);

    const {mentions, ...opt} = options
    const extraProps = {
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
        ...opt
    };

    return <Mentions
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
}