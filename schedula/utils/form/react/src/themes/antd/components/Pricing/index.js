import React from 'react';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import QueueAnim from 'rc-queue-anim';
import TweenOne from 'rc-tween-one';
import {Row, Col} from 'antd';

function Pricing({children, render, img, ...props}) {

    const animType = {
        queue: 'right',
        one: {
            x: '-=30',
            opacity: 0,
            type: 'from',
            ease: 'easeOutQuad',
        },
    };
    img = 'https://gw.alipayobjects.com/mdn/rms_ae7ad9/afts/img/A*OnyWT4Nsxy0AAAAAAAAAAABjARQnAQ'
    console.log(children)
    return (
        <div {...props}>
            <Row className="pricing">
                <Col md={12} xs={24} key="img">
                    <span className="pricing-img" name="image">
                        <img src={img} width="100%" alt="img"/>
                    </span>
                </Col>
                <Col md={12} xs={24}>
                    <img src={img} width="100%" alt="img"/>
                </Col>
            </Row>
        </div>
    );
}

export default Pricing;