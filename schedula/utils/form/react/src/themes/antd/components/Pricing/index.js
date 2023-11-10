import React from 'react';
import {OverPack} from 'rc-scroll-anim';
import QueueAnim from 'rc-queue-anim';
import TweenOne from 'rc-tween-one';
import {Row, Col} from 'antd';
import './index.css'
import {createLayoutElement} from "../../../../core/fields/utils";
import isObject from "lodash/isObject";

function Pricing(
    {
        children,
        render,
        title,
        img,
        pricing,
        button,
        isMobile = false,
        enableOverPack = true,
        ...props
    }
) {
    const animType = {
        queue: isMobile ? 'bottom' : 'right',
        one: isMobile ? {
            scaleY: '+=0.3',
            opacity: 0,
            type: 'from',
            ease: 'easeOutQuad',
        } : {
            x: '-=30',
            opacity: 0,
            type: 'from',
            ease: 'easeOutQuad',
        }
    };
    const items = [
        img !== undefined ? <TweenOne
            key="img"
            animation={animType.one}
            resetStyle
            className={'pricing-img-wrapper'}
            component={Col}
            componentProps={{
                md: 12,
                xs: 24,
            }}>
            {isObject(img) ? createLayoutElement({
                key: 'img',
                layout: img,
                render,
                isArray: false
            }) : <span className={'pricing-img'}>
                        <img src={img} width="100%" alt="img"/>
                    </span>}
        </TweenOne> : null,
        <QueueAnim
            key="text"
            type={animType.queue}
            leaveReverse
            ease={['easeOutQuad', 'easeInQuad']}
            className={'pricing-text-wrapper'}
            component={Col}
            componentProps={{
                md: 12,
                xs: 24,
            }}>
            {title !== undefined ?
                isObject(title) ? createLayoutElement({
                    key: 'title',
                    layout: title,
                    render,
                    isArray: false
                }) : <h1 key={'title'} className={'pricing-title'}>
                    {title}
                </h1> : null
            }
            {(children || []).length ?
                <div key={'content'} className={'pricing-content'}>
                    {children}
                </div> : null
            }
            {pricing !== undefined ?
                isObject(pricing) ? createLayoutElement({
                    key: 'pricing',
                    layout: pricing,
                    render,
                    isArray: false
                }) : <div key={'pricing'} className={'pricing-pricing'}>
                    {pricing}
                </div> : null
            }
            {button !== undefined ?
                createLayoutElement({
                    key: 'button',
                    layout: button,
                    render,
                    isArray: false
                }) : null
            }
        </QueueAnim>
    ]
    return (
        <div className={'pricing-wrapper'} {...props}>
            {enableOverPack ? <OverPack component={Row} className={'pricing'}>
                {items}
            </OverPack> : <Row className={'pricing'}>{items}</Row>}
        </div>
    );
}

export default Pricing;