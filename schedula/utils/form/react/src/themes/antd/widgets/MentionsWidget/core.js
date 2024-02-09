import React from "react";
import {Mentions} from "antd";
import {ariaDescribedByIds, labelValue} from "@rjsf/utils";

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

    const handleChange = ({nextValue}) =>
        onChange(nextValue);

    const handleBlur = () => onBlur(id, value);

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
            value={value}
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