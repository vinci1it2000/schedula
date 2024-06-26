import React from 'react';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import QueueAnim from 'rc-queue-anim';
import TweenOne from 'rc-tween-one';
import {Row, Col} from 'antd';
import {getChildrenToRender} from './utils';

function Pricing0(props) {
    const {...tagProps} = props;
    const {dataSource, isMobile} = tagProps;
    delete tagProps.dataSource;
    delete tagProps.isMobile;
    const animType = {
        queue: isMobile ? 'bottom' : 'right',
        one: isMobile
            ? {
                scaleY: '+=0.3',
                opacity: 0,
                type: 'from',
                ease: 'easeOutQuad',
            }
            : {
                x: '-=30',
                opacity: 0,
                type: 'from',
                ease: 'easeOutQuad',
            },
    };
    return (
        <div {...tagProps} {...dataSource.wrapper}>
            <OverPack component={Row} {...dataSource.OverPack}>
                <TweenOne
                    key="img"
                    animation={animType.one}
                    resetStyle
                    {...dataSource.imgWrapper}
                    component={Col}
                    componentProps={{
                        md: dataSource.imgWrapper.md,
                        xs: dataSource.imgWrapper.xs,
                    }}
                >
          <span {...dataSource.img}>
            <img src={dataSource.img.children} width="100%" alt="img"/>
          </span>
                </TweenOne>
                <QueueAnim
                    key="text"
                    type={animType.queue}
                    leaveReverse
                    ease={['easeOutQuad', 'easeInQuad']}
                    {...dataSource.childWrapper}
                    component={Col}
                    componentProps={{
                        md: dataSource.childWrapper.md,
                        xs: dataSource.childWrapper.xs,
                    }}
                >
                    {dataSource.childWrapper.children.map(getChildrenToRender)}
                </QueueAnim>
            </OverPack>
        </div>
    );
}

export default Pricing0;
