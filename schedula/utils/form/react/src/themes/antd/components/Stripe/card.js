/*
 * # -*- coding: utf-8 -*-
 * #
 * # Copyright 2024 sinapsi - s.r.l.;
 * # Licensed under the EUPL (the 'Licence');
 * # You may not use this work except in compliance with the Licence.
 * # You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
 *
 */

import React, {useState, useMemo, useRef, useEffect} from 'react';
import {
    Card,
    Flex,
    Typography,
    Statistic,
    Button,
    theme,
    Badge,
    Timeline,
    Drawer,
    ConfigProvider
} from 'antd';
import {CheckCircleFilled} from '@ant-design/icons';
import {useLocaleStore} from "../../models/locale";
import {getComponents} from '../../../../core'
import './card.css'

const {Title, Text, Paragraph} = Typography
const PricingCard = (
    {
        children,
        render: {uiSchema, registry, formContext},
        title,
        productDescription,
        priceDescription,
        priceUnit,
        buttonText,
        titleFeatures,
        ribbon,
        ribbonProps,
        price,
        quantity,
        currency = "€",
        features,
        urlCreateCheckoutSession = "/stripe/create-checkout-session",
        urlCreateCheckoutStatus = "/stripe/session-status",
        checkoutProps,
        onCheckout,
        buttonProps,
        maxProductDescriptionHeight = 50,
        ...props
    }
) => {
    const {token} = theme.useToken();
    const {form: {state: {language}}} = formContext
    const [openCheckout, setOpenCheckout] = useState(false)
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Stripe.Card')
    const Stripe = getComponents({
        render: {formContext}, component: 'Stripe'
    })
    const separators = useMemo(() => {
        const numberFormat = new Intl.NumberFormat(language.replace('_', '-'));
        const parts = numberFormat.formatToParts(1234567.89);
        const groupSeparator = parts.find(part => part.type === 'group').value;
        const decimalSeparator = parts.find(part => part.type === 'decimal').value;
        return {groupSeparator, decimalSeparator};
    }, [language]);
    const [parentHeight, setParentHeight] = useState(0);
    const parentRef = useRef(null);

    useEffect(() => {
        if (parentRef.current) {
            setParentHeight(parentRef.current.clientHeight);
        }
    }, []);
    return <ConfigProvider theme={{
        "components": {
            "Statistic": {"contentFontSize": token.fontSizeHeading2},
            "Timeline": {"tailColor": "transparent"}
        }
    }}>
        <Badge.Ribbon
            key={"ribbon-card"}
            className={ribbon || (ribbonProps || {}).text ? "" : "ribbon-hide"}
            rootClassName={"ribbon-stretch"} text={ribbon} {...ribbonProps}>
            <Card
                key="card"
                styles={{
                    body: {
                        margin: 34,
                        width: 240,
                        padding: 0,
                        alignSelf: "stretch"
                    }
                }} {...props}>
                <Flex gap={"large"} vertical style={{height: "100%"}}
                      ref={parentRef}>
                    {title ?
                        <Title key="title" level={4} style={{margin: 0}}>
                            {title}
                        </Title> : null}
                    <Text
                        style={{
                            flexGrow: 1,
                            height: parentHeight >= 200 ? maxProductDescriptionHeight : undefined,
                            maxHeight: parentHeight >= 200 ? maxProductDescriptionHeight : undefined
                        }}
                        key="product-description"
                        type="secondary">
                        {productDescription || ""}
                    </Text>
                    {price !== undefined ?
                        <Flex gap="small" align="flex-end">
                            <Statistic
                                key="value"
                                valueStyle={{"fontWeight": 700}}
                                value={price}
                                suffix={` ${currency}`}
                                {...separators}
                            />
                            {priceUnit ? <Text
                                key="price-uint"
                                type="secondary">
                                {priceUnit || ""}
                            </Text> : null}
                        </Flex> : null}
                    {priceDescription ? <Text key="price-description">
                        {priceDescription}
                    </Text> : null}
                    <Button
                        key="button"
                        size="large"
                        type="primary"
                        style={{width: '100%'}}
                        onClick={() => setOpenCheckout(true)}
                        {...buttonProps}>
                        {buttonText || locale.buttonText}
                    </Button>
                    {features ?
                        <Text key="title-features">
                            {titleFeatures || locale.titleFeatures}
                        </Text> : null}
                    {features ? <Timeline
                        rootClassName={"timeline-compact"}
                        key="features"
                        items={features.map(({text, ...item}) => ({
                            color: token.colorTextTertiary,
                            dot: <CheckCircleFilled/>,
                            children: <Text>{text}</Text>,
                            ...item
                        }))}
                    /> : null}
                </Flex>
            </Card>
        </Badge.Ribbon>
        <Drawer
            key="modal"
            title={locale.modalTitle}
            destroyOnClose
            height="100%"
            placement="bottom"
            footer={null}
            open={openCheckout}
            onClose={() => setOpenCheckout(false)}>
            <Stripe
                render={{formContext, uiSchema, registry}}
                urlCreateCheckoutSession={urlCreateCheckoutSession}
                urlCreateCheckoutStatus={urlCreateCheckoutStatus}
                checkoutProps={checkoutProps}
                onCheckout={(data) => {
                    if (onCheckout)
                        onCheckout(data)
                    setOpenCheckout(false)
                }}/>
        </Drawer>
    </ConfigProvider>
};
export default PricingCard;