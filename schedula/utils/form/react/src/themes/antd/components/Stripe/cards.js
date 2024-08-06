/*
 * # -*- coding: utf-8 -*-
 * #
 * # Copyright 2024 sinapsi - s.r.l.;
 * # Licensed under the EUPL (the 'Licence');
 * # You may not use this work except in compliance with the Licence.
 * # You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
 *
 */

import React, {useMemo, useState} from 'react';
import {Flex, theme, Segmented} from 'antd';
import {getComponents} from '../../../../core'
import get from 'lodash/get'

const {useToken} = theme;

const PricingCards = (
    {
        children,
        render,
        prices = [],
        options,
        categoryMax={},
        initialSelected = 0,
        style = {},
        ...props
    }
) => {
    const {token} = useToken();
    const {formContext} = render
    const StripeCard = getComponents({
        render: {formContext}, component: 'Stripe.Card'
    })
    const [current, setCurrent] = useState(initialSelected)
    const max = {...categoryMax}
    prices.forEach(
        ({price, quantity = 1, months = 1, category=null}) => {
            const ratio = price / quantity / months
            if (!isNaN(ratio)) {
                max[category] = get(max, category, [])
                max[category].push(ratio)
            }
        }
    )
    Object.keys(max).forEach(k => {
        max[k] = Math.max(...max[k])
    })
    const cards = useMemo(() => (
        prices.map((
            {
                price,
                quantity = 1,
                months = 1,
                category=null,
                ribbonText = 'Save',
                ...item
            }, index) => {
            const ratio = price / quantity / months
            const saving = Math.ceil(10000 - ratio / max[category] * 10000) / 100
            item = saving ? {
                ribbon: `${ribbonText} ${saving}%`,
                ribbonProps: {color: token.colorSuccess}, ...item
            } : item
            return <StripeCard
                key={index}
                render={render}
                price={price}
                quantity={quantity}
                style={{alignSelf: "stretch", display: "flex"}}
                {...item}/>
        })
    ), [prices, max, StripeCard])

    if (options) {
        return <Flex key={"container"} vertical justify="center" align="center"
                     gap="middle">
            <Segmented
                key={"options"}
                options={options.map((item, index) => ({value: index, ...item}))}
                onChange={setCurrent} size="large"
                value={current}
            />
            {options.map((item, key) => {
                let _style = key !== current ? {
                    ...style,
                    display: "none"
                } : style
                return <Flex key={key} wrap gap={"middle"} justify={"center"}
                             align={"center"} style={_style} {...props}>
                    {item.children.map(index => cards[index])}
                </Flex>
            })}
        </Flex>
    }
    return <Flex key={"container"} wrap gap="middle" justify="center"
                 align="center" style={style}{...props}>
        {cards}
    </Flex>
};
export default PricingCards;